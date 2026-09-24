# Infrastructure (CDK)

Four stacks: encrypted storage, the Cognito user pool and sign-in triggers, the
SES sender identity, and the HTTP API with its Lambdas.

The stacks are Python, in `portal/`, with `app.py` as the entry point. The CDK
command line is a Node program, which is why `npx` appears below and why
`package.json` exists at all.

Setup and deployment are in the repository README. The normal way to deploy is
the one command there, run from the repository root, which checks the config,
SES and Bedrock first and points the website at the result:

    python scripts/deployment/deploy.py --env dev

To work on the stacks themselves, the underlying CDK commands run from here:

    npx cdk diff   --all -c env=dev
    npx cdk deploy --all -c env=dev

Everything account- or environment-specific lives in `config/<env>.json`, never
in stack code, which is what lets the same code deploy to a personal dev
account and to Emory's without edits.
