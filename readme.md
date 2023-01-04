# GCP Workload Identity Federation: AWS, Lambda, SDK

This is an AWS Lambda case of a multi project set of examples for configuring Google Cloud Workload Identity Federation. For further information on this set-up please refer to Google's documentation here: https://cloud.google.com/iam/docs/configuring-workload-identity-federation#aws

## Google Disclaimer
This is not an officially supported Google product

## Table of Contents
1. [Prerequisites](https://github.com/dreardon/gcp-workload-identity-federation-aws-lambda-sdk#prerequisites)
1. [Google Service Account and Identity Pool](https://github.com/dreardon/gcp-workload-identity-federation-aws-lambda-sdk#create-a-google-service-account-and-identity-pool)
1. [AWS IAM Role Creation](https://github.com/dreardon/gcp-workload-identity-federation-aws-lambda-sdk#aws-role-creation)
1. [Connect Identity Pool to AWS](https://github.com/dreardon/gcp-workload-identity-federation-aws-lambda-sdk#connect-identity-pool-to-aws-create-provider)
1.  [Create Client Configuration File](https://github.com/dreardon/gcp-workload-identity-federation-aws-lambda-sdk#create-client-configuration-file)
1. [Deploy Sample Lambda Function](https://github.com/dreardon/gcp-workload-identity-federation-aws-lambda-sdk#deploy-sample-lambda-function)
1. [Validate Workload Identity Federation Setup](https://github.com/dreardon/gcp-workload-identity-federation-aws-lambda-sdk#validate-workload-identity-federation-pool-setup)

## Prerequisites
<ul type="square"><li>An existing Google Project, you'll need to reference PROJECT_ID later in this setup</li>
<li>Enabled services</li>

```bash
gcloud services enable iamcredentials.googleapis.com
gcloud services enable vision.googleapis.com
```
</ul>

## Create a Google Service Account and Identity Pool
```bash
export PROJECT_ID=[Google Project ID]
export PROJECT_NUMBER=[Google Project Number]
export SERVICE_ACCOUNT=[Google Service Account Name] #New Service Account for Workload Identity
export WORKLOAD_IDENTITY_POOL=[Workload Identity Pool] #New Workload Identity Pool Name

gcloud config set project $PROJECT_ID

gcloud iam service-accounts create $SERVICE_ACCOUNT \
    --display-name="AWS Lambda Workload Identity SA"

# Defines what this service account can do once assumed by AWS
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/visionai.admin"

gcloud iam workload-identity-pools create $WORKLOAD_IDENTITY_POOL \
    --location="global" \
--description="Workload Identity Pool for AWS Lambda" \
--display-name="AWS Lambda Workload Pool"
```

## AWS Role Creation

```bash
export AWS_ROLE_NAME=[AWS Role Name] #New Role for Future Lambda

cat > policy-document.json << ENDOFFILE
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
ENDOFFILE

aws iam create-role --role-name $AWS_ROLE_NAME  \
    --assume-role-policy-document file://policy-document.json  \
    --description "Role used to send images to GCP Vision API"

export ROLE_ARN=$(aws iam get-role --role-name $AWS_ROLE_NAME \
--query 'Role.[RoleName, Arn]' --output text | awk '{print $2}')
```
![AWS Role Permission Tab](images/aws_permissions.png)
![AWS Role Trust Tab](images/aws_trust.png)

## Create Client Configuration File
```bash
gcloud iam workload-identity-pools create-cred-config \
    projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/providers/$PROVIDER_ID \
    --service-account="$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
    --aws \
    --output-file=client-config.json
```
NOTE: Do not use the --enable-imdsv2 flag here, you can use this when generating the client config file for use on EC2s.
Ensure this file is packaged with your Lambda function.

## Connect Identity Pool to AWS, Create Provider

```bash
export WORKLOAD_PROVIDER=[Workload Identity Provider] #New Workload Provider Name
export AWS_ACCOUNT_ID=[AWS Account ID] 

#Allows the AWS role attached to Lambda to use the previously created GCP service account
gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$WORKLOAD_IDENTITY_POOL/attribute.aws_role/arn:aws:sts::$AWS_ACCOUNT_ID:assumed-role/$AWS_ROLE_NAME"

gcloud iam workload-identity-pools providers create-aws $WORKLOAD_PROVIDER  \
  --location="global"  \
  --workload-identity-pool=$WORKLOAD_IDENTITY_POOL \
  --account-id="$AWS_ACCOUNT_ID" \
  --attribute-mapping="google.subject=assertion.arn","attribute.aws_role=assertion.arn.contains('assumed-role') ? assertion.arn.extract('{account_arn}assumed-role/') + 'assumed-role/' + assertion.arn.extract('assumed-role/{role_name}/') : assertion.arn"
```

## Deploy Sample Lambda Function

### Python 3.7
```bash
export LAMBDA_FUNCTION_NAME="Sample_GCP_Vision_API_SDK"

docker run -v "$PWD":/var/task "public.ecr.aws/sam/build-python3.7" \
/bin/sh -c "pip install google-cloud-vision -t python/; \
exit"

zip -r9 ./google-cloud-vision.zip ./python

LAYER_URI=$(aws lambda publish-layer-version --layer-name google-cloud-vision \
      --description "Google Vision SDK package" \
      --zip-file fileb://./google-cloud-vision.zip \
      --compatible-runtimes python3.7 \
      --query 'LayerVersionArn' --output text | cut -d/ -f1)

zip lambda_function.zip workload_identity.py client-config.json

aws lambda create-function --function-name "$LAMBDA_FUNCTION_NAME" \
--zip-file fileb://lambda_function.zip \
--handler workload_identity.lambda_handler \
--runtime python3.7 \
--role arn:aws:iam::$AWS_ACCOUNT_ID:role/$AWS_ROLE_NAME \
--layers $LAYER_URI \
--timeout 900 \
--environment "Variables={PROJECT_ID=$PROJECT_ID,PROJECT_NUMBER=$PROJECT_NUMBER,POOL_ID=$WORKLOAD_IDENTITY_POOL,PROVIDER_ID=$WORKLOAD_PROVIDER,SERVICE_ACCOUNT=$SERVICE_ACCOUNT,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_APPLICATION_CREDENTIALS='client-config.json'}"
```

### Python 3.9 (TBD)
Still a work in progress: 
- ~~Lambda layer needs to be uploaded via S3 storage since it exceeds the size limitations.~~
- Working to address a "cannot import name 'cygrpc' from 'grpc._cython'" error.

```bash
export LAMBDA_FUNCTION_NAME="Sample_GCP_Vision_API_SDK"

docker run -v "$PWD":/var/task "public.ecr.aws/sam/build-python3.9" \
/bin/sh -c "pip install google-cloud-vision -t python/; \
exit"

zip -r9 ./google-cloud-vision.zip ./python

#Create bucket, if necessary, and upload zip layer
aws s3 mb s3://lambda-layers-gcp
aws s3 cp google-cloud-vision.zip s3://lambda-layers-gcp/

LAYER_URI=$(aws lambda publish-layer-version --layer-name google-cloud-vision \
      --description "Google Vision SDK package" \
      --content S3Bucket="lambda-layers-gcp",S3Key="google-cloud-vision.zip" \
      --compatible-runtimes python3.9 \
      --query 'LayerVersionArn' --output text | cut -d/ -f1)

zip lambda_function.zip workload_identity.py client-config.json

aws lambda create-function --function-name "$LAMBDA_FUNCTION_NAME" \
--zip-file fileb://lambda_function.zip \
--handler workload_identity.lambda_handler \
--runtime python3.9 \
--role arn:aws:iam::$AWS_ACCOUNT_ID:role/$AWS_ROLE_NAME \
--layers $LAYER_URI \
--timeout 900 \
--environment "Variables={PROJECT_ID=$PROJECT_ID,PROJECT_NUMBER=$PROJECT_NUMBER,POOL_ID=$WORKLOAD_IDENTITY_POOL,PROVIDER_ID=$WORKLOAD_PROVIDER,SERVICE_ACCOUNT=$SERVICE_ACCOUNT,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_APPLICATION_CREDENTIALS='client-config.json'}"
```

## Validate Workload Identity Federation Pool Setup
![Vision API Validation](images/validate.png)

## For More Detail
https://github.com/salrashid123/gcpcompat-aws