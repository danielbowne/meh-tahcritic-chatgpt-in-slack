from aws_cdk import core as cdk
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_events as events
from aws_cdk import aws_lambda_event_sources as event_sources

class SlackChatGPTBotStack(cdk.Stack):
    def __init__(self, scope: cdk.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # IAM role
        role = iam.Role(self, 'Role',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com')
        )

        # Allow lambda invoke permissions
        role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                'lambda:InvokeFunction',
                'lambda:InvokeAsync'
            ],
            resources=['*']
        ))

        # Allow S3 bucket access
        bucket = s3.Bucket.from_bucket_name(self, 'Bucket', bucket_name=cdk.Fn.ref('SLACK_INSTALLATION_S3_BUCKET_NAME'))
        bucket.grant_read_write(role)
        
        bucket_state = s3.Bucket.from_bucket_name(self, 'BucketState', bucket_name=cdk.Fn.ref('SLACK_STATE_S3_BUCKET_NAME'))
        bucket_state.grant_read_write(role)

        openai_bucket = s3.Bucket.from_bucket_name(self, 'OpenAIBucket', bucket_name=cdk.Fn.ref('OPENAI_S3_BUCKET_NAME'))
        openai_bucket.grant_read_write(role)

        # Lambda function
        function = _lambda.Function(self, 'Function',
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler='app_prod.handler',
            code=_lambda.Code.from_asset('path/to/app'),
            role=role,
            timeout=cdk.Duration.seconds(12),
            environment={
                'SERVERLESS_STAGE': cdk.Fn.find_in_map('Environments', cdk.Fn.ref('AWS::Region'), 'stage'),
                'SLACK_SIGNING_SECRET': cdk.Fn.ref('SLACK_SIGNING_SECRET'),
                'SLACK_CLIENT_ID': cdk.Fn.ref('SLACK_CLIENT_ID'),
                'SLACK_CLIENT_SECRET': cdk.Fn.ref('SLACK_CLIENT_SECRET'),
                'SLACK_SCOPES': cdk.Fn.ref('SLACK_SCOPES'),
                'SLACK_INSTALLATION_S3_BUCKET_NAME': cdk.Fn.ref('SLACK_INSTALLATION_S3_BUCKET_NAME'),
                'SLACK_STATE_S3_BUCKET_NAME': cdk.Fn.ref('SLACK_STATE_S3_BUCKET_NAME'),
                'OPENAI_S3_BUCKET_NAME': cdk.Fn.ref('OPENAI_S3_BUCKET_NAME'),
                'OPENAI_TIMEOUT_SECONDS': '10'
            }
        )

        # API Gateway
        api = apigw.HttpApi(self, 'Api')
        api.add_routes(
            path='/slack/events',
            methods=[apigw.HttpMethod.POST],
            integration=integrations.LambdaProxyIntegration(handler=function)
        )

        api.add_routes(
            path='/slack/install',
            methods=[apigw.HttpMethod.GET],
            integration=integrations.LambdaProxyIntegration(handler=function)
        )

        api.add_routes(
            path='/slack/oauth_redirect',
            methods=[apigw.HttpMethod.GET],
            integration=integrations.LambdaProxyIntegration