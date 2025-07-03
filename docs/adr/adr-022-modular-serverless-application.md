# Executive Summary
This document proposes the technical architecture for a serverless application built on AWS using the Serverless Application Model (SAM). The primary goal is to create a highly modular system where distinct business domains (Authentication, Partners, Contracts, etc.) are developed, deployed, and maintained independently. This approach minimizes inter-module dependencies, accelerates development cycles, and enhances overall system scalability and resilience.

The architecture is centered around AWS Lambda, API Gateway, and DynamoDB. We will enforce a strict separation of concerns by adopting a layered software design within each module, including handlers, services, and repositories. Each business module will have its own dedicated API Gateway for complete domain isolation, while a shared module will manage common resources, primarily the DynamoDB tables (domain models) and data access repositories, which will be consumed by all other business modules. PynamoDB, a Python ORM for DynamoDB, will be utilized to provide a clean, object-oriented interface for data persistence.

# High-Level Architecture
The overall system consists of independent business modules, each with its own dedicated API Gateway for complete domain isolation. Each module contains Lambda functions specific to that business domain and interacts with a shared data layer composed of DynamoDB tables. This architecture enables independent deployment, scaling, and management of each business domain.

```
+------------------+             +------------------+         +------------------+
|   Authz API GW   |             |  Partner API GW  |   ...   |Transaction API GW|
|authz.api.com/v1/ |             |partner.api.com/v1/|         |txn.api.com/v1/   |
+------------------+             +------------------+         +------------------+
         |                                 |                                 |
         v                                 v                                 v
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

- `template.yaml`: Defines all shared AWS::DynamoDB::Table resources. It uses CloudFormation Outputs to export the names/ARNs of these resources so they can be referenced by other modules.
- `domain/models.py`: Contains PynamoDB classes that map to your DynamoDB tables (e.g., ContractModel, PartnerModel).
- `domain/repositories.py`: Implements the Repository Pattern using PynamoDB, abstracting database queries.
- `utilities/`: A collection of stateless helper functions.

## Business Modules (e.g., partner, contract)
These modules contain the application logic and are deployed as independent SAM stacks. Each module has complete autonomy over its API interface and deployment lifecycle.

template.yaml:

Defines AWS::Serverless::Function resources and a dedicated AWS::Serverless::Api resource for the module.

Each module has its own API Gateway, providing complete domain isolation and independent API management.

Uses CloudFormation !ImportValue to get the names/ARNs of shared DynamoDB tables from the shared module.

Defines an AWS::Serverless::LayerVersion that packages the entire shared directory's code, making the domain models, repositories, and utilities available to the Lambda functions.

## SAM Template Strategy for Dedicated API Gateways
Here is the concrete implementation strategy for dedicated API Gateways per business module while sharing data resources.

### Step 1: Define Shared Data Resources Only

In shared/template.yaml, you define only the shared data infrastructure (DynamoDB tables). Each business module will manage its own API Gateway independently.

```
# shared/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: >
  Shared data resources for the modular application, including DynamoDB tables and common utilities.

Resources:
  # Define shared DynamoDB tables
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

  ContractTable:
    Type: AWS::DynamoDB::Table
    Properties:
      AttributeDefinitions:
        - AttributeName: contractId
          AttributeType: S
      KeySchema:
        - AttributeName: contractId
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

Outputs:
  # Export the Table Names for other stacks to use
  PartnerTableName:
    Description: "Name of the Partner DynamoDB Table"
    Value: !Ref PartnerTable
    Export:
      Name: !Sub "${AWS::StackName}-PartnerTableName"

  ContractTableName:
    Description: "Name of the Contract DynamoDB Table"
    Value: !Ref ContractTable
    Export:
      Name: !Sub "${AWS::StackName}-ContractTableName"

```

### Step 2: Define Dedicated API Gateway per Business Module

In each business module (e.g., partner/template.yaml), you define your own API Gateway and functions while importing shared data tables from the shared stack.

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

Globals:
  Api:
    Cors:
      AllowMethods: "'*'"
      AllowHeaders: "'*'"
      AllowOrigin: "'*'"

Resources:
  # Dedicated API Gateway for Partner module
  PartnerApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: v1
      DefinitionBody:
        swagger: '2.0'
        info:
          title: 'Partner Management API'
          version: '1.0'
        paths: {} # Paths defined by Lambda function events

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
            # Attach this event to the DEDICATED Partner API Gateway
            RestApiId: !Ref PartnerApi
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
            # Attach this event to the SAME dedicated Partner API Gateway
            RestApiId: !Ref PartnerApi
            Path: /partners
            Method: POST

Outputs:
  # Export the Partner API endpoint for external access
  PartnerApiEndpoint:
    Description: "Partner API Gateway endpoint URL"
    Value: !Sub "https://${PartnerApi}.execute-api.${AWS::Region}.amazonaws.com/v1"
    Export:
      Name: !Sub "${AWS::StackName}-PartnerApiEndpoint"
```


# Deployment Strategy
The deployment strategy emphasizes independence while maintaining shared data consistency.

**Shared Data Stack First:** The shared module must be deployed first to create the DynamoDB tables and common resources.

```
cd shared/
sam build
sam deploy --stack-name your-app-shared --capabilities CAPABILITY_IAM --guided
```

**Independent Module Deployment:** Any business module can then be deployed independently with its own API Gateway. The SAM CLI will automatically resolve the !ImportValue references from the running your-app-shared stack.

```
cd partner/
sam build --use-container
sam deploy --stack-name your-app-partner --capabilities CAPABILITY_IAM --guided
```

**Parallel Development and Deployment:** Since each module has its own API Gateway, multiple teams can develop and deploy their modules in parallel without coordination, as long as the shared data stack is deployed first.

```
# Team A can deploy Partner module
cd partner/
sam deploy --stack-name partner-module-prod

# Team B can deploy Contract module simultaneously  
cd contract/
sam deploy --stack-name contract-module-prod

# Team C can deploy Transaction module independently
cd transaction/
sam deploy --stack-name transaction-module-prod
```

This approach creates a clean separation of API interfaces and business logic while sharing data infrastructure, fully realizing the goal of a modular, independently deployable serverless application with domain isolation.

## Benefits and Trade-offs of Dedicated API Gateways

### Benefits

**Complete Domain Isolation:**
- Each business domain has full control over its API specification, versioning, and evolution
- API changes in one domain do not affect other domains
- Independent security policies and rate limiting per domain

**Independent Deployment and Scaling:**
- Teams can deploy API changes without coordinating with other teams
- API Gateway throttling and caching can be configured per business domain
- Each domain can scale independently based on its specific traffic patterns

**Enhanced Security Boundaries:**
- Domain-specific authentication and authorization policies
- Isolated WAF rules and security configurations per API
- Separate CloudWatch logs and monitoring per domain

**Simplified API Management:**
- Each domain can have its own API documentation and developer portal
- Domain-specific custom domain names (e.g., `partners.api.company.com`, `contracts.api.company.com`)
- Independent API versioning strategies per business domain

**Team Autonomy:**
- Development teams have full ownership of their API lifecycle
- No cross-team dependencies for API Gateway configuration changes
- Independent testing and staging environments per domain

### Trade-offs

**Increased Infrastructure Complexity:**
- More API Gateway instances to manage and monitor
- Slightly higher AWS costs (though minimal for API Gateway)
- More CloudFormation stacks to maintain

**API Discovery and Consistency:**
- Requires additional effort to maintain API consistency across domains
- May need centralized API catalog or documentation portal
- Cross-domain API calls require multiple base URLs

**Monitoring and Observability:**
- Distributed monitoring across multiple API Gateways
- Need for centralized dashboard to view overall system health
- More complex distributed tracing across domain boundaries

### Mitigation Strategies

**For Infrastructure Complexity:**
- Use consistent naming conventions and tagging across all API Gateways
- Implement Infrastructure as Code (SAM/CloudFormation) templates for standardization
- Create shared deployment pipelines and automation

**For API Consistency:**
- Establish API design standards and guidelines across teams
- Implement automated API specification validation
- Create shared OpenAPI specification templates

**For Monitoring:**
- Implement centralized logging and monitoring dashboard
- Use AWS X-Ray for distributed tracing across all domains
- Create standardized CloudWatch metrics and alarms across all API Gateways

