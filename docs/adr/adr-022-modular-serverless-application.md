# Executive Summary
This document proposes the technical architecture for a serverless application built on AWS using the Serverless Application Model (SAM). The primary goal is to create a highly modular system where distinct business domains (Authentication, Partners, Contracts, etc.) are developed, deployed, and maintained independently. This approach minimizes inter-module dependencies, accelerates development cycles, and enhances overall system scalability and resilience.

The architecture is centered around AWS Lambda, API Gateway, and DynamoDB. We will enforce a strict separation of concerns by adopting a layered software design within each module, including handlers, services, and repositories. A dedicated shared module will manage common resources, primarily the DynamoDB tables (domain models), a shared API Gateway, and data access repositories, which will be consumed by all other business modules. PynamoDB, a Python ORM for DynamoDB, will be utilized to provide a clean, object-oriented interface for data persistence.

# High-Level Architecture
The overall system will consist of a single API Gateway endpoint that routes requests to different sets of Lambda functions based on the URL path. Each set of functions corresponds to a specific business module. These modules interact with a shared data layer composed of DynamoDB tables.

```
                               +-----------------------------------+
                               |        Shared API Gateway         |
                               |  (e.g., api.yourapp.com/v1/...)   |
                               +-----------------------------------+
                                  |         |         |         |
      /authz/* ------------------+         |         |         +------------------- /transaction/*
         |                                 |         |                                 |
         v                                 v         v                                 v
+------------------+             +------------------+         +------------------+
|  Authz Module    |             |  Partner Module  |   ...   | Transaction Module|
| (Lambda Functions)|             | (Lambda Functions)|         | (Lambda Functions)|
+------------------+             +------------------+         +------------------+
         |                                 |                                 |
         |         +-----------------------+-----------------------+         |
         |         |                                               |         |
         v         v                                               v         v
+------------------------------------------------------------------------------------+
|                                  Shared Resources                                  |
|------------------------------------------------------------------------------------|
|   +--------------------------+                      +--------------------------+   |
|   |   DynamoDB Tables        |                      |   Repositories & Models  |   |
|   | (Partner, Contract, etc.)|                      |    (PynamoDB ORM)        |   |
|   +--------------------------+                      +--------------------------+   |
+------------------------------------------------------------------------------------+

```

# Project Structure
To facilitate modularity and independent deployments, we will adopt a monorepo structure. Each business concern will reside in its own top-level directory, alongside a shared directory for common infrastructure and code.

```
/your-project-root
├── shared/
│   ├── template.yaml             # Defines shared resources (API Gateway, DynamoDB Tables).
│   ├── domain/
│   │   ├── models.py             # PynamoDB model definitions for all tables.
│   │   └── repositories.py       # Repository classes for data access.
│   └── utilities/
│       ├── encryption.py         # Helper for encryption/decryption.
│       ├── validators.py         # Data validation helpers.
│       └── ...
│
├── authz/
│   ├── template.yaml             # SAM template for the 'authz' module.
│   ├── src/
│   │   ├── handlers.py           # Lambda handlers (API entry points).
│   │   ├── services.py           # Business logic implementation.
│   │   ├── dtos.py               # Data Transfer Objects for API contracts.
│   │   └── mappers.py            # Maps between DTOs and Domain Models.
│   ├── requirements.txt
│   └── tests/
│
├── partner/
│   └── ... (and so on for all other modules)
│
└── ...

```


# Module Architecture & Shared Resources
## shared Module
This is the foundational module. It defines the core infrastructure that will be used by all business modules.

- `template.yaml`: Defines all shared AWS::DynamoDB::Table resources and the single AWS::Serverless::Api resource. It uses CloudFormation Outputs to export the names/ARNs of these resources so they can be referenced by other modules.
- `domain/models.py`: Contains PynamoDB classes that map to your DynamoDB tables (e.g., ContractModel, PartnerModel).
- `domain/repositories.py`: Implements the Repository Pattern using PynamoDB, abstracting database queries.
- `utilities/`: A collection of stateless helper functions.

## Business Modules (e.g., partner, contract)
These modules contain the application logic and are deployed as independent SAM stacks.

template.yaml:

Defines AWS::Serverless::Function resources.

Crucially, it does NOT define a new API Gateway. Instead, it references the shared API and adds its endpoints to it.

Uses CloudFormation !ImportValue to get the IDs/ARNs of the shared API Gateway and DynamoDB tables.

Defines an AWS::Serverless::LayerVersion that packages the entire shared directory's code, making the domain models, repositories, and utilities available to the Lambda functions.

## SAM Template Strategy for a Shared API Gateway
Here is the concrete implementation strategy for sharing the API Gateway across modules.

### Step 1: Define and Export the API in the shared Module

In shared/template.yaml, you define the API Gateway resource and export its ID. This template is deployed once (or whenever shared resources change).

```
# shared/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: >
  Shared resources for the modular application, including the central API Gateway and DynamoDB tables.

Globals:
  Api:
    Cors:
      AllowMethods: "'*'"
      AllowHeaders: "'*'"
      AllowOrigin: "'*'"

Resources:
  # Define the single, shared API Gateway for the entire application
  SharedApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      StageName: v1
      DefinitionBody:
        swagger: '2.0'
        info:
          title: 'MyApplication API'
        paths: {} # Paths are defined in the downstream business modules

  # Define a DynamoDB table
  PartnerTable:
    Type: AWS::DynamoDB::Table
    Properties:
      AttributeDefinitions:
        - AttributeName: partnerId
          AttributeType: S
      KeySchema:
        - AttributeName: partnerId
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

Outputs:
  # Export the API Gateway ID so other stacks can reference it
  SharedApiGatewayId:
    Description: "The ID of the shared API Gateway"
    Value: !Ref SharedApiGateway
    Export:
      Name: !Sub "${AWS::StackName}-SharedApiGatewayId"

  # Export the Table Name for other stacks to use
  PartnerTableName:
    Description: "Name of the Partner DynamoDB Table"
    Value: !Ref PartnerTable
    Export:
      Name: !Sub "${AWS::StackName}-PartnerTableName"

```

### Step 2: Reference the Shared API in Business Modules

In each business module (e.g., partner/template.yaml), you define your functions and attach them to the shared API Gateway by importing the value you exported from the shared stack.

```
# partner/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: >
  Partner module. Contains all business logic and API endpoints for managing partners.

Parameters:
  SharedStackName:
    Type: String
    Default: "your-app-shared" # The name of the deployed shared stack

Resources:
  # Lambda Layer containing the shared code (repositories, models, etc.)
  SharedCodeLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      ContentUri: ../shared/
      CompatibleRuntimes:
        - python3.9
    Metadata:
      BuildMethod: python3.9

  # Lambda function to get a partner by ID
  GetPartnerFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: handlers.get_partner_by_id
      Runtime: python3.9
      Layers:
        - !Ref SharedCodeLayer
      Environment:
        Variables:
          # Import the partner table name from the shared stack output
          PARTNER_TABLE_NAME: !ImportValue 
            'Fn::Sub': '${SharedStackName}-PartnerTableName'
      Policies:
        # Grant this function read access to the specific DynamoDB table
        - DynamoDBCrudPolicy:
            TableName: !ImportValue 
              'Fn::Sub': '${SharedStackName}-PartnerTableName'
      Events:
        GetPartnerApi:
          Type: Api
          Properties:
            # Attach this event to the SHARED API Gateway
            RestApiId: !ImportValue
              'Fn::Sub': '${SharedStackName}-SharedApiGatewayId'
            Path: /partners/{partnerId}
            Method: GET

  # Lambda function to create a new partner
  CreatePartnerFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: handlers.create_partner
      Runtime: python3.9
      Layers:
        - !Ref SharedCodeLayer
      Environment:
        Variables:
          PARTNER_TABLE_NAME: !ImportValue 
            'Fn::Sub': '${SharedStackName}-PartnerTableName'
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !ImportValue 
              'Fn::Sub': '${SharedStackName}-PartnerTableName'
      Events:
        CreatePartnerApi:
          Type: Api
          Properties:
            # Attach this event to the SAME shared API Gateway
            RestApiId: !ImportValue
              'Fn::Sub': '${SharedStackName}-SharedApiGatewayId'
            Path: /partners
            Method: POST
```


# Deployment Strategy
The deployment order is critical.

**Shared Stack First:** The shared module must be deployed first to create the API Gateway and DynamoDB tables.


```
cd shared/
sam build
sam deploy --stack-name your-app-shared --capabilities CAPABILITY_IAM --guided
```

**Independent Module Deployment:** Any business module can then be deployed. The SAM CLI will automatically resolve the !ImportValue references from the running your-app-shared stack.

```
cd partner/
sam build --use-container
sam deploy --stack-name your-app-partner --capabilities CAPABILITY_IAM --guided
```

This approach creates a clean separation of infrastructure from business logic, fully realizing the goal of a modular, independently deployable serverless application.

