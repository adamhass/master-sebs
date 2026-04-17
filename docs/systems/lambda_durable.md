# Lambda Durable + DynamoDB

## Architecture

```
Client → API Gateway (HTTPS) → Lambda (Python 3.13, durable_config) → DynamoDB
                                    ↕
                            Checkpoint Log (SDK-managed)
```

Extension of baseline. Same Lambda compute model, adds AWS Durable Execution SDK for checkpoint/replay durability. DynamoDB replaces Redis as state store — fully serverless stack (no VPC needed).

## Implementation

**Terraform** (`integrations/baseline/aws/lambda_durable.tf`): Extends baseline stack. New Lambda function with `durable_config { execution_timeout = 300, retention_period = 1 }`. DynamoDB table (PAY_PER_REQUEST, partition key `state_key`). Separate IAM role with DynamoDB + `AWSLambdaBasicDurableExecutionRolePolicy`. API Gateway route `POST /durable` pointing to published Lambda alias (required — durable functions cannot be invoked via $LATEST).

**Benchmark function** (`lambda_durable_package/handler.py`): Uses `@durable_step` decorator for state operations + `context.step()` for checkpointed execution. Write = DynamoDB PutItem inside durable step (checkpointed). Read = DynamoDB GetItem inside durable step (checkpointed). Compute loop outside steps (deterministic, no checkpoint needed).

**SDK pattern verified from source**:
```python
@durable_step           # returns closure: fn(StepContext) -> T
def write_state(step_context, key, size_kb):
    # DynamoDB write + timing
    return latency_us

# context.step() receives closure, executes, checkpoints result
write_lat = context.step(write_state(key, size_kb))
```

**State mechanism**: DynamoDB PutItem/GetItem wrapped in durable steps. Each step creates a checkpoint in Lambda's execution log. On replay (after failure), completed steps return cached results without re-executing. State shared across invocations via DynamoDB.

**Invocation**: `POST https://<api-gw-id>.execute-api.eu-north-1.amazonaws.com/durable`

## Design Decisions

- DynamoDB over Redis: fully serverless, no VPC needed, pay-per-request. Each system uses native state mechanism.
- Published alias required: durable functions reject $LATEST invocations. Terraform creates `live` alias.
- Provider upgrade 5.x → 6.x: `durable_config` block requires AWS provider >= 6.25.0.
- Compute outside steps: deterministic code doesn't need checkpointing — saves 1 checkpoint round-trip.

## Limitations Found

- **DynamoDB 400KB item limit**: 512KB state blob exceeds hard limit. All 200 invocations failed. Fundamental constraint — production would use S3 for large objects.
- **Cold start 3329ms**: ~7x heavier than baseline Lambda (473ms). Durable SDK initialization + DynamoDB client bootstrap + checkpoint client setup.
- **~6x slower than baseline**: DynamoDB write (~12ms) + checkpoint overhead vs Redis (~2ms) with no checkpoint. Cost of durability.
- **Checkpoint serialization**: Step return values must be JSON-serializable. Binary blobs in DynamoDB use Binary type but step return is just the latency integer (no blob in checkpoint).

## Thesis Framing

Not "Lambda Durable is bad" — it's "external-service durability has measurable cost vs embedded durability." Lambda Durable's model (bolt durability onto existing FaaS) pays network tax on every checkpoint. Restate's model (build durability into runtime) avoids it.

This IS the finding. Exactly what the thesis argues: architecture matters more than feature parity.
