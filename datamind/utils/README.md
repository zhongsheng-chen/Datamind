# model
model_id = generate_id(
    prefix="mdl",
    keys=(name,),
)

# version
version_id = generate_id(
    prefix="ver",
    keys=(
        model_id,
        version,
    ),
)

# deployment
deployment_id = generate_id(
    prefix="dep",
    keys=(
        model_id,
        environment,
    ),
)

# experiment
experiment_id = generate_id(
    prefix="exp",
    keys=(
        model_id,
        experiment_name,
    ),
)

# routing
routing_id = generate_id(
    prefix="rte",
    keys=(
        deployment_id,
        strategy,
    ),
)

# assignment
assignment_id = generate_id(
    prefix="asg",
    keys=(
        request_id,
        model_id,
    ),
)

# audit
audit_id = generate_id(
    prefix="aud",
    keys=(
        event.trace_id,
        event.request_id,
        event.action,
    ),
)