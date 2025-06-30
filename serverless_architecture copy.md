# ADR-001: Migration from Modular Monolith to Serverless Pipeline Architecture

## Status
**Proposed** - Under Review

## Date
2025-01-16

## Context

### Current State: PINET Core (Old Architecture)

PINET Core implements a **multi-layered architecture** combining several architectural styles:

#### **Architecture Styles Applied:**

1. **Domain Driven Design (DDD)**
   - Business logic organized around domain concepts (Authentication, Subscription Charges, Disputes, etc.)
   - Domain models encapsulate business rules and invariants
   - Clear separation between domain logic and infrastructure concerns

2. **Model-View-Controller (MVC) - Rails Pattern**
   - Controllers handle HTTP requests and coordinate between layers
   - Models represent domain entities and business logic
   - Views handle presentation (API responses)

3. **Event-Driven Architecture**
   - Asynchronous processing via Sidekiq background jobs
   - Event publishing and subscription within the monolith
   - Event-based communication between modules

4. **Layered Architecture (CLEAN Architecture)**
   - **Presentation Layer**: Rails controllers and API endpoints
   - **Application Layer**: Service objects and use cases
   - **Domain Layer**: Business entities and domain services
   - **Infrastructure Layer**: Database access, external APIs

#### **System Structure:**

- **Framework**: Ruby on Rails 7 with Packwerk for modularity
- **Central Event Processing**: Single endpoint `api/v1/events` with delegation pattern
- **Database Strategy**: Multi-database setup with PostgreSQL
- **Event System**: In-process pub/sub with Sidekiq for background jobs
- **Deployment**: Traditional server-based deployment with containers

#### **Business Components:**
1. **Authentication**: Custom OIDC layer for user authentication
2. **Subscription Charge**: Transaction contract processing and transmission
3. **Dispute**: Dispute contract processing through the network
4. **Reconciliation**: Partner data reconciliation via contracts and events
5. **Settlement**: Partner settlement processing through contracts and events

#### **Processing Flow (Layered Delegation):**
```
HTTP Request → api/v1/events
    ↓
[Receive Event Layer]
    ↓
[Validate Event Layer]
    ↓
[Delegate to Processor Layer]
    ↓
[Business Logic Processing]
    ↓
[Generate Outgoing Event]
    ↓
[Transportation Component] → External Partners
```

### Target State: Moneta Core (New Architecture)

Moneta Core implements a **pipeline-oriented serverless architecture** with multiple architectural styles:

#### **Architecture Styles Applied:**

1. **Service-Oriented Architecture (SOA) - Serverless FaaS**
   - Each business function implemented as independent Lambda functions
   - Functions expose well-defined interfaces via API Gateway
   - Loose coupling between services through event-driven communication

2. **Microservices Architecture**
   - Each business domain (Authentication, Subscription, Dispute, etc.) as separate services
   - Independent deployment and scaling per service
   - Service-specific data stores and business logic

3. **Event-Driven Architecture**
   - AWS EventBridge for inter-service communication
   - Event streaming with SNS/SQS for asynchronous processing
   - Event sourcing patterns for audit trails

4. **Pipeline Architecture (Pipe-and-Filter)**
   - Dedicated processing pipelines for each business function
   - Each pipeline as an end-to-end processing chain
   - Filters for validation, transformation, and business logic
   - Direct partner integration without cross-component dependencies

#### **System Structure:**

- **Framework**: AWS Lambda with Python 3.9
- **Pipeline-per-Domain**: Dedicated endpoints and processing chains
- **Database Strategy**: DynamoDB with single-table design patterns
- **Event System**: AWS EventBridge, SNS, SQS for inter-service communication
- **Deployment**: Infrastructure as Code using AWS SAM

#### **Business Pipeline Architecture:**

1. **Authentication Pipeline**: `api/v1/auth/*`
   - OIDC authentication flow
   - User management and token validation

2. **Subscription Charge Pipeline**: `api/v1/events/subscription_charges`
   ```
   Event Input → Validate Contract → Sign Contract → Direct Partner Delivery
   ```

3. **Dispute Pipeline**: `api/v1/events/disputes`
   ```
   Dispute Event → Validate Terms → Process Dispute → Partner Notification
   ```

4. **Reconciliation Pipeline**: `api/v1/events/reconciliations`
   ```
   Reconciliation Request → Data Validation → Matching Logic → Partner Response
   ```

5. **Settlement Pipeline**: `api/v1/events/settlements`
   ```
   Settlement Event → Contract Validation → Processing → Partner Settlement
   ```

#### **Processing Flow (End-to-End Pipelines):**
```
HTTP Request → api/v1/events/{domain}
    ↓
[Domain-Specific Lambda Function] ← Shared Layer Components
    ↓
[Validate Contract] → [Process Business Logic] → [Direct Partner Integration]
    ↓
[Response/Event Publishing]
```

#### **Shared Layer Architecture:**

The new architecture implements a **shared layer strategy** that balances code reuse with pipeline flexibility:

```
shared/
├── domain/              # Domain Models (Database Record Wrappers ONLY)
│   ├── mpass_model.py           # Pure data structures
│   ├── organization_model.py    # No business logic
│   ├── publisher_model.py       # Just data representation
│   └── enum.py
├── repositories/        # Data Access Patterns (CRUD Operations ONLY)
│   ├── mpass_repository.py      # Generic database operations
│   ├── organization_repository.py
│   └── repositories.py
├── services/           # Infrastructure Services (NOT Business Logic)
│   ├── contract_verification_service.py    # Generic signature verification
│   ├── event_delivery_service.py           # Generic partner communication
│   └── base_service.py
├── common/             # Shared Infrastructure Components
│   ├── input_validator.py       # Generic JSON/schema validation
│   ├── event_transformer.py     # Generic event format conversion
│   └── crypto_utilities.py      # Generic cryptographic functions
└── utilities/          # Cross-Pipeline Utilities
    ├── validators.py            # Generic validation utilities
    ├── env_config.py           # Environment configuration
    └── logging_utils.py         # Standardized logging
```

**Infrastructure Components Available to All Pipelines:**
- **Contract Verification Service**: Generic signature verification (not business rules)
- **Event Delivery Service**: Generic partner communication (not domain logic)
- **Input Validator**: Generic JSON/schema validation (not business validation)
- **Domain Models**: Pure data structure representations (no business methods)
- **Repository Layer**: Generic CRUD operations (not business queries)
- **Utilities**: Environment config, logging, generic validators

### Business Drivers

1. **Scalability Requirements**: Need to handle variable workloads with automatic scaling
2. **Cost Optimization**: Pay-per-use model for sporadic usage patterns
3. **Operational Overhead**: Reduce infrastructure management and maintenance
4. **Time-to-Market**: Faster deployment cycles and feature delivery
5. **Resilience**: Built-in fault tolerance and disaster recovery
6. **Global Reach**: Multi-region deployment capabilities

## Decision

**We will migrate from the Ruby on Rails modular monolith architecture to a serverless pipeline architecture using AWS Lambda and managed services.**

This migration will be executed in phases:

1. **Phase 1**: Core authentication services (auth-service)
2. **Phase 2**: Organization and membership management
3. **Phase 3**: Event processing and pipeline orchestration
4. **Phase 4**: Legacy system decommissioning

## Rationale

### Technical Advantages

#### 1. **Pipeline Architecture Benefits**
- **End-to-End Processing**: Each business domain has dedicated processing pipeline without cross-dependencies
- **Filter Composition**: Pipe-and-filter pattern allows flexible composition of processing stages
- **Parallel Processing**: Multiple pipelines can process different domains simultaneously
- **Resource Optimization**: Each pipeline function gets exactly the resources it needs

#### 2. **Microservices & SOA Advantages**
- **Domain Isolation**: Each business function (Authentication, Subscription, Dispute, etc.) runs independently
- **Independent Scaling**: Auto-scaling from 0 to thousands of concurrent executions per domain
- **Technology Flexibility**: Each service can use optimal technology stack for its domain
- **Team Autonomy**: Independent deployment and development cycles per business domain

#### 3. **Event-Driven Architecture Enhancement**
- **Domain-Specific Events**: EventBridge routing based on business domain rather than technical delegation
- **Direct Integration**: Events flow directly to appropriate pipelines without central processing
- **Event Sourcing**: Complete audit trail of all business events per domain
- **Asynchronous Processing**: SNS/SQS for reliable event delivery and retry mechanisms

#### 4. **Serverless FaaS Benefits**
- **Cold Start Mitigation**: Modern Lambda runtime optimizations reduce cold start impact
- **Stateless Design**: Pure functions with no shared state between invocations
- **Automatic Scaling**: Functions scale independently based on domain-specific load patterns
- **Cost Efficiency**: Pay only for actual processing time per business function

#### 5. **Infrastructure as Code (IaC)**
- **Pipeline-as-Code**: Each business pipeline defined as infrastructure
- **Reproducible Deployments**: SAM templates ensure consistent environments per domain
- **Version Control**: Infrastructure changes tracked alongside domain-specific code
- **Independent Rollbacks**: Rollback individual pipelines without affecting others

#### 6. **Developer Experience Enhancement**
- **Domain-Focused Development**: Developers can focus on single business domain
- **Local Pipeline Testing**: SAM CLI provides local testing capabilities per pipeline
- **CI/CD Per Domain**: Independent deployment pipelines for each business function
- **Distributed Observability**: CloudWatch + X-Ray tracing per pipeline with domain-specific metrics

### Operational Benefits

#### 1. **Cost Efficiency**
```
Modular Monolith Costs:
- Always-on servers: $500-2000/month baseline
- Database servers: $200-800/month
- Load balancers: $20-50/month
- Maintenance overhead: 20-30% development time

Serverless Pipeline Costs:
- Lambda execution: Pay per 100ms increments
- DynamoDB: Pay per read/write capacity units
- API Gateway: Pay per API call
- Estimated 40-60% cost reduction for typical workloads
```

#### 2. **Operational Overhead Reduction**
- **No Server Management**: AWS manages underlying infrastructure
- **Automatic Patching**: Runtime updates handled by AWS
- **Built-in Monitoring**: CloudWatch integration out-of-the-box
- **Security**: AWS security model with IAM and VPC integration

#### 3. **Deployment & Delivery**
- **Independent Deployments**: Each service can be deployed independently
- **Faster Iterations**: Smaller deployment units enable faster feedback cycles
- **Canary Deployments**: Built-in support for gradual rollouts

### Architectural Comparison

| Aspect | Multi-Layered Monolith (Old) | Pipeline-Oriented Serverless (New) |
|--------|-------------------------------|-------------------------------------|
| **Primary Patterns** | DDD + MVC + Layered + Event-Driven | SOA + Microservices + Pipeline + Event-Driven |
| **Processing Model** | Central delegation with layered processing | Domain-specific end-to-end pipelines |
| **Business Logic Organization** | Domain services within monolith layers | Independent pipeline functions per domain |
| **Deployment Unit** | Single Rails application | Individual Lambda functions per pipeline |
| **Scaling** | Vertical/horizontal server scaling | Automatic function-level scaling per pipeline |
| **Data Storage** | PostgreSQL with multiple DBs | DynamoDB with domain-optimized tables |
| **Event Processing** | Sidekiq background jobs + in-process delegation | EventBridge + SNS/SQS + direct integration |
| **Request Flow** | `api/v1/events` → delegate → process → transport | `api/v1/events/{domain}` → pipeline → direct delivery |
| **Cross-Domain Dependencies** | Shared transportation layer | Independent pipelines with minimal coupling |
| **Local Development** | `rails server` + dependencies | `sam local` + Docker per service |
| **State Management** | In-memory + database transactions | Stateless functions + DynamoDB |
| **Inter-service Communication** | In-process method calls + shared DB | API Gateway + Event-driven messaging |
| **Monitoring** | Application-level logging | CloudWatch + X-Ray distributed tracing per pipeline |
| **Contract Processing** | Centralized validation and delegation | Pipeline-specific contract handling |

### Shared Layer Implementation Strategy

#### **Design Principles for Shared Components**

The shared layer follows specific rules and conventions to maintain the balance between code reuse and pipeline flexibility:

##### **1. Three-Tier Shared Architecture**

```python
# Domain Layer - Database Record Wrappers
class MPassModel(BaseDynamoModel):
    """Pure data model representing mPass database record"""
    mPassId: str
    status: MPassStatus
    tier: MPassTier
    # No business logic - only data structure and validation

# Repository Layer - Data Access Collections  
class MPassRepository(BaseRepository):
    """Manages mPass database operations and queries"""
    def get_by_id(self, mpass_id: str) -> Optional[MPassModel]:
        # Standardized query patterns
    
    def save(self, mpass: MPassModel) -> MPassModel:
        # Standardized persistence operations

# Service Layer - Business Domain Logic
class ContractService(BaseService):
    """Reusable contract operations across pipelines"""
    def validate_subscription_contract(self, contract: dict) -> bool:
        # Business logic that can be reused by multiple pipelines
    
    def sign_contract(self, contract: dict) -> dict:
        # Cryptographic operations shared across domains
```

##### **2. Shared Component Rules & Conventions**

**Rule 1: Domain Models (shared/domain/)**
- **Purpose**: Represent database records as Python objects
- **Convention**: Models are pure data structures with validation only
- **Flexibility**: Each pipeline can extend models with domain-specific methods
- **Example Usage**:
```python
# In subscription_charge_pipeline.py
from shared.domain.mpass_model import MPassModel
from shared.domain.organization_model import OrganizationModel

def process_subscription(event):
    mpass = MPassModel(**event['mpass_data'])
    organization = OrganizationModel(**event['org_data'])
    # Pipeline-specific logic here
```

**Rule 2: Repository Layer (shared/repositories/)**
- **Purpose**: Standardize database access patterns and queries
- **Convention**: One repository per domain model, consistent interface
- **Flexibility**: Pipelines can inject custom query logic while maintaining base patterns
- **Example Usage**:
```python
# In dispute_pipeline.py
from shared.repositories.mpass_repository import MPassRepository

def handle_dispute(event):
    mpass_repo = MPassRepository()
    mpass = mpass_repo.get_by_id(event['mpass_id'])
    # Dispute-specific processing logic
    mpass_repo.save(updated_mpass)
```

**Rule 3: Shared Services (shared/services/)**
- **Purpose**: Provide infrastructure and utility services (NOT business logic)
- **Convention**: Services are stateless, generic, and infrastructure-focused
- **Flexibility**: Pipelines use shared utilities but implement their own business logic
- **What Goes in Shared Services**:
```python
# shared/services/contract_verification_service.py ✅ SHARED INFRASTRUCTURE
class ContractVerificationService:
    def verify_contract_signature(self, contract: dict) -> bool:
        """Generic signature verification - works for ANY contract type"""
        # Only verifies cryptographic signature, no business validation
        return self._verify_digital_signature(contract)

# shared/services/event_delivery_service.py ✅ SHARED INFRASTRUCTURE  
class EventDeliveryService:
    def deliver_to_partner(self, event: dict, partner_config: dict) -> bool:
        """Generic partner communication - works for ANY event type"""
        # Generic HTTP/messaging, no business logic
        return self._send_to_partner_endpoint(event, partner_config)
```

**How Pipelines Use Shared Services**:
```python
# settlement_pipeline/settlement_handler.py ❌ PIPELINE CODE (NOT in shared)
from shared.services.contract_verification_service import ContractVerificationService
from shared.services.event_delivery_service import EventDeliveryService

def process_settlement(event):
    # ✅ Use shared infrastructure service for signature verification
    verification_service = ContractVerificationService()
    
    # Step 1: Verify signature using shared infrastructure
    if not verification_service.verify_contract_signature(event):
        raise InvalidSignatureError("Contract signature is invalid")
    
    # Step 2: ❌ Business validation stays IN THE PIPELINE - NOT shared
    validated_contract = verify_contract(event, settlement_rules)
    
    # Step 3: ❌ Contract signing stays IN THE PIPELINE - NOT shared  
    signed_contract = sign_contract(validated_contract, settlement_signing_rules)
    
    # Step 4: ✅ Use shared infrastructure service for delivery
    delivery_service = EventDeliveryService()
    delivery_service.deliver_to_partner(signed_contract)

def verify_contract(event, settlement_rules):
    """❌ PIPELINE-SPECIFIC: Business rules, template validation, etc."""
    # Settlement-specific business validation:
    # - Minimum settlement amounts
    # - Authorized parties
    # - Contract template compliance
    # - Settlement timeframes
    pass

def sign_contract(contract, settlement_signing_rules):
    """❌ PIPELINE-SPECIFIC: Settlement-specific signing logic"""
    # Settlement-specific signing requirements:
    # - Settlement authority signatures
    # - Settlement-specific crypto algorithms
    # - Settlement compliance stamps
    pass
```

##### **3. AWS SAM Layer Integration**

```yaml
# SAM template for shared layer deployment
SharedLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: moneta-shared-layer
    Description: Shared components for all pipelines
    ContentUri: shared/
    CompatibleRuntimes:
      - python3.9
    RetentionPolicy: Retain

# Pipeline functions reference the shared layer
SubscriptionChargeFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: subscription_charge.lambda_handler
    Layers:
      - !Ref SharedLayer
    Environment:
      Variables:
        SHARED_LAYER_PATH: /opt/python
```

##### **4. Balance Strategy: Reuse vs. Flexibility**

**Code Reuse Mechanisms:**
- **Inheritance**: Base classes for common patterns
- **Composition**: Injectable services and utilities
- **Configuration**: Environment-driven behavior adaptation

**Flexibility Preservation:**
- **Interface Contracts**: Well-defined APIs with implementation freedom
- **Extension Points**: Hook methods for pipeline-specific logic
- **Override Capabilities**: Ability to replace shared components when needed

**Example: Flexible Contract Validation**
```python
# Shared base with extensibility
class BaseContractValidator:
    def validate(self, contract: dict) -> ValidationResult:
        # Common validation logic
        result = self._validate_structure(contract)
        result.update(self._validate_business_rules(contract))
        return result
    
    def _validate_business_rules(self, contract: dict) -> ValidationResult:
        # Extension point for pipeline-specific rules
        return ValidationResult(valid=True)

# Pipeline-specific extension
class SubscriptionContractValidator(BaseContractValidator):
    def _validate_business_rules(self, contract: dict) -> ValidationResult:
        # Subscription-specific validation logic
        return self._validate_subscription_limits(contract)
```

##### **5. Shared Layer DO's and DON'Ts**

#### **✅ DO: Put in Shared Layer**

**Infrastructure & Utilities:**
```python
# ✅ Generic contract signature verification (infrastructure)
class ContractVerificationService:
    def verify_contract_signature(self, contract: dict) -> bool:
        # Generic signature verification - Single Responsibility Principle
        # ONLY verifies crypto signature, no business validation

# ✅ Generic event delivery (infrastructure)  
class EventDeliveryService:
    def deliver_to_partner(self, event: dict, partner_config: dict) -> bool:
        # Generic partner communication - reusable

# ✅ Generic input validation (utility)
class InputValidator:
    def validate_json_structure(self, data: dict, schema: dict) -> bool:
        # Generic JSON validation - reusable
```

**Data Access Patterns:**
```python
# ✅ Domain models (data structure)
class MPassModel(BaseDynamoModel):
    mPassId: str
    status: MPassStatus  # Pure data representation

# ✅ Repository patterns (data access)
class MPassRepository(BaseRepository):
    def get_by_id(self, mpass_id: str) -> Optional[MPassModel]:
        # Generic CRUD operations - reusable
```

#### **❌ DON'T: Put in Shared Layer**

**Business Logic Specific to One Domain:**
```python
# ❌ Settlement-specific contract verification (business rules + templates)
def verify_contract(event, settlement_rules):
    # This belongs ONLY in settlement_pipeline - don't share!
    # - Minimum settlement amounts
    # - Authorized parties validation  
    # - Settlement template compliance
    # - Settlement timeframes

# ❌ Dispute-specific contract verification (business rules + templates)
def verify_contract(event, dispute_rules):
    # This belongs ONLY in dispute_pipeline - don't share!
    # - Dispute evidence requirements
    # - Dispute timeframe validation
    # - Dispute template compliance
    # - Resolution criteria

# ❌ Subscription-specific contract verification (business rules + templates)
def verify_contract(event, subscription_rules):
    # This belongs ONLY in subscription_pipeline - don't share!
    # - Subscription tier validation
    # - Payment rules compliance
    # - Subscription template validation
    # - Terms and conditions
```

**Pipeline-Specific Workflows:**
```python
# ❌ Each pipeline has its own verify_contract with different rules
# settlement_pipeline/verify_contract.py
def verify_contract(event, settlement_rules):
    # Settlement-specific contract rules - don't pollute other pipelines!
    # e.g., minimum settlement amount, authorized parties, etc.

# dispute_pipeline/verify_contract.py  
def verify_contract(event, dispute_rules):
    # Dispute-specific contract rules - different from settlement rules!
    # e.g., dispute timeframes, evidence requirements, etc.

# subscription_pipeline/verify_contract.py
def verify_contract(event, subscription_rules):
    # Subscription-specific contract rules - unique business logic!
    # e.g., subscription tiers, payment validation, etc.
```

#### **📋 Quick Decision Matrix**

| Component Type | Shared Layer? | Where It Belongs |
|---------------|---------------|------------------|
| Contract signature verification (crypto) | ✅ YES | `shared/services/contract_verification_service.py` |
| Event delivery to partners | ✅ YES | `shared/services/event_delivery_service.py` |
| Domain models (data structures) | ✅ YES | `shared/domain/` |
| Database repositories | ✅ YES | `shared/repositories/` |
| Contract signing | ❌ NO | `{pipeline}/sign_contract.py` |
| Contract verification (business rules) | ❌ NO | `{pipeline}/verify_contract.py` |
| Contract template validation | ❌ NO | `{pipeline}/verify_contract.py` |
| Settlement contract signing | ❌ NO | `settlement_pipeline/sign_contract.py` |
| Settlement contract verification | ❌ NO | `settlement_pipeline/verify_contract.py` |
| Dispute contract signing | ❌ NO | `dispute_pipeline/sign_contract.py` |
| Dispute contract verification | ❌ NO | `dispute_pipeline/verify_contract.py` |
| Subscription contract signing | ❌ NO | `subscription_pipeline/sign_contract.py` |
| Subscription contract verification | ❌ NO | `subscription_pipeline/verify_contract.py` |
| Pipeline workflows | ❌ NO | Individual pipeline modules |

#### **🎯 Implementation Guidelines**

**For Pipeline Developers:**
1. **Keep business logic in your pipeline** - don't pollute shared layer
2. **Use shared infrastructure services** for common operations (signing, delivery)
3. **Use shared domain models** for data consistency
4. **Use shared repositories** for database operations
5. **Contribute generic utilities only** to shared layer

**For Shared Layer Maintainers:**
1. **Only accept infrastructure and utilities** - reject business logic
2. **Keep interfaces generic and reusable** across all domains
3. **Provide clear extension points** for customization
4. **Document what belongs in shared vs pipeline** 
5. **Version shared components** for backward compatibility

### Architectural Style Application Comparison

#### **Old Architecture: How Styles Are Applied**

1. **Domain Driven Design (DDD)**
   ```ruby
   # Domain models encapsulate business rules
   class SubscriptionCharge < ApplicationRecord
     validates :amount, :currency, presence: true
     
     def process_charge
       # Domain logic for charge processing
     end
   end
   
   # Domain services handle complex business operations
   class SubscriptionChargeService
     def process_transaction_contract(contract)
       # Business logic implementation
     end
   end
   ```

2. **MVC Pattern Implementation**
   ```ruby
   # Controller handles HTTP requests and orchestration
   class Api::V1::EventsController < ApplicationController
     def create
       event = IncomingEvent.create!(event_params)
       EventProcessorService.delegate(event)
       render json: { status: 'accepted' }
     end
   end
   ```

3. **Layered Architecture (CLEAN)**
   ```
   ┌─────────────────────────────────────┐
   │     Presentation Layer              │ ← Controllers, API endpoints
   │  (Rails Controllers & Views)        │
   ├─────────────────────────────────────┤
   │     Application Layer               │ ← Service objects, Use cases
   │  (Service Classes & Orchestration)  │
   ├─────────────────────────────────────┤
   │     Domain Layer                    │ ← Business entities, Domain services
   │  (Models, Domain Services)          │
   ├─────────────────────────────────────┤
   │     Infrastructure Layer            │ ← Database, External APIs
   │  (ActiveRecord, HTTP clients)       │
   └─────────────────────────────────────┘
   ```

4. **Central Event Processing Flow**
   ```ruby
   # Single entry point with delegation
   class EventProcessorService
     def self.delegate(event)
       case event.event_type
       when 'subscription_charge'
         SubscriptionChargeService.process(event)
       when 'dispute'
         DisputeService.process(event)
       # ... other delegations
       end
       
       TransportationService.deliver_outgoing_events
     end
   end
   ```

#### **New Architecture: How Styles Are Applied**

1. **Service-Oriented Architecture (SOA) with Serverless FaaS**
   ```python
   # Each business function as independent Lambda
   # subscription_charge_handler.py
   def lambda_handler(event, context):
       """Dedicated handler for subscription charges"""
       contract = validate_subscription_contract(event)
       signed_contract = sign_contract(contract)
       deliver_to_partner(signed_contract)
       return {"statusCode": 200}
   ```

2. **Microservices Architecture**
   ```yaml
   # Each domain gets its own infrastructure
   SubscriptionChargeService:
     Type: AWS::Serverless::Function
     Properties:
       Handler: subscription_charge.lambda_handler
       Environment:
         Variables:
           SUBSCRIPTION_TABLE: !Ref SubscriptionTable
   
   DisputeService:
     Type: AWS::Serverless::Function
     Properties:
       Handler: dispute.lambda_handler
       Environment:
         Variables:
           DISPUTE_TABLE: !Ref DisputeTable
   ```

3. **Pipeline Architecture (Pipe-and-Filter)**
   ```python
   # End-to-end pipeline for subscription charges
   def subscription_charge_pipeline(event):
       """Pipe-and-filter pattern implementation"""
       # Filter 1: Input validation
       validated_event = validate_input(event)
       
       # Filter 2: Contract processing
       contract = process_contract(validated_event)
       
       # Filter 3: Digital signing
       signed_contract = apply_digital_signature(contract)
       
       # Filter 4: Partner delivery
       delivery_result = deliver_to_partner(signed_contract)
       
       # Filter 5: Audit logging
       log_transaction(delivery_result)
       
       return delivery_result
   ```

4. **Domain-Specific Pipeline Routing**
   ```yaml
   # API Gateway routes directly to domain pipelines
   Events:
     /api/v1/events/subscription_charges:
       post:
         x-amazon-apigateway-integration:
           httpMethod: POST
           type: aws_proxy
           uri: !Sub "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:SubscriptionChargeFunction"
   
     /api/v1/events/disputes:
       post:
         x-amazon-apigateway-integration:
           httpMethod: POST
           type: aws_proxy
           uri: !Sub "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:DisputeFunction"
   ```

### Migration Strategy Benefits

#### 1. **From Centralized Delegation to Pipeline Specialization**
- **Old**: Single `api/v1/events` endpoint with internal routing and shared transportation
- **New**: Domain-specific endpoints with end-to-end processing pipelines
- **Benefit**: Eliminates cross-domain dependencies and reduces processing latency

#### 2. **Domain-Driven Design Evolution**
- **Preservation**: Business domain concepts remain intact across architectures
- **Enhancement**: Each domain gets dedicated infrastructure and independent scaling
- **Benefit**: True domain isolation with bounded contexts

#### 3. **Pipeline Pattern Advantages**
- **Scalability**: Each pipeline stage can scale independently
- **Maintainability**: Clear separation of concerns within each pipeline
- **Testability**: Each filter/stage can be tested in isolation
- **Performance**: Direct processing without delegation overhead

#### 4. **Technology Stack Modernization**
- Python 3.9 with modern libraries (Pydantic, Boto3)
- Type hints and better tooling ecosystem
- AWS-native development patterns

## Consequences

### Positive Outcomes

1. **Improved Scalability**
   - Automatic scaling from 0 to thousands of concurrent executions
   - No capacity planning required
   - Better handling of traffic spikes

2. **Cost Optimization**
   - Pay-per-use pricing model
   - No idle resource costs
   - Reduced operational overhead

3. **Faster Development Cycles**
   - Independent service deployments
   - Smaller, focused codebases
   - Parallel development streams

4. **Enhanced Reliability**
   - Built-in fault tolerance
   - Multi-AZ deployments by default
   - Automatic retry mechanisms

5. **Better Observability**
   - Distributed tracing with X-Ray
   - Centralized logging with CloudWatch
   - Rich metrics and alarms

### Negative Consequences & Mitigations

1. **Complexity Increase**
   - **Challenge**: More distributed components to manage
   - **Mitigation**: Comprehensive documentation, ADRs, and standardized patterns

2. **Cold Start Latency**
   - **Challenge**: Initial function invocation delays
   - **Mitigation**: Provisioned concurrency for critical paths, function warming strategies

3. **Local Development Complexity**
   - **Challenge**: Testing distributed systems locally
   - **Mitigation**: SAM CLI, LocalStack, comprehensive unit testing

4. **Vendor Lock-in**
   - **Challenge**: AWS-specific services and patterns
   - **Mitigation**: Abstraction layers, adherence to standard patterns, exit strategy documentation

5. **Learning Curve**
   - **Challenge**: Team needs to learn serverless patterns and AWS services
   - **Mitigation**: Training programs, pair programming, gradual migration approach

### Risk Assessment & Mitigation

| Risk | Impact | Probability | Mitigation Strategy |
|------|---------|-------------|-------------------|
| Cold start performance issues | Medium | Medium | Provisioned concurrency, function optimization |
| Debugging complexity | Medium | High | Comprehensive logging, X-Ray tracing, local dev tools |
| AWS service limits | High | Low | Monitor quotas, request limit increases proactively |
| Team knowledge gap | Medium | High | Training program, documentation, mentoring |
| Data migration complexity | High | Medium | Phased migration, data validation, rollback procedures |

## Implementation Plan

### Phase 1: Foundation & Shared Layer (Weeks 1-6)
**Infrastructure Setup:**
- Set up AWS accounts and IAM structure
- Implement shared infrastructure (VPC, security groups)
- Create CI/CD pipelines

**Shared Layer Development:**
- Implement shared domain models (mpass_model.py, organization_model.py, etc.)
- Create base repository patterns and database access layer
- Develop core shared services (contract validation, event processing)
- Set up AWS Lambda Layer for shared components
- Establish shared layer versioning and deployment strategy

**Foundation Services:**
- Implement auth-service core functionality using shared layer
- Create shared contract signing and cryptographic services
- Establish event delivery mechanisms

### Phase 2: Core Pipeline Implementation (Weeks 7-14)
**Authentication Pipeline:**
- Complete auth-service with full OIDC implementation
- Implement user management using shared domain models
- Set up authentication-specific contract validation

**Subscription Charge Pipeline:**
- Implement `api/v1/events/subscription_charges` endpoint
- Build end-to-end subscription processing pipeline
- Integrate shared contract validator and signing services
- Implement direct partner delivery using shared event delivery

**Shared Layer Evolution:**
- Refine shared services based on pipeline usage patterns
- Add pipeline-specific extension points
- Document shared component usage guidelines

### Phase 3: Business Domain Pipelines (Weeks 15-22)
**Dispute Pipeline:**
- Implement `api/v1/events/disputes` endpoint
- Build dispute processing pipeline using shared services
- Extend shared contract validator for dispute-specific rules

**Reconciliation Pipeline:**
- Implement `api/v1/events/reconciliations` endpoint
- Build data reconciliation pipeline
- Leverage shared repository patterns for data matching

**Settlement Pipeline:**
- Implement `api/v1/events/settlements` endpoint
- Build settlement processing pipeline
- Utilize shared contract and event services

**Shared Layer Optimization:**
- Consolidate common patterns across pipelines
- Optimize shared layer performance and caching
- Implement shared monitoring and alerting utilities

### Phase 4: Migration, Integration & Optimization (Weeks 23-30)
**Data Migration:**
- Migrate data from PostgreSQL to DynamoDB using shared domain models
- Validate data consistency across all pipelines
- Implement shared data migration utilities

**System Integration:**
- Set up EventBridge routing between pipelines
- Implement cross-pipeline event communication using shared event services
- Performance optimization across all pipelines

**Legacy Decommissioning:**
- Gradual traffic migration from old central delegation to new pipelines
- Monitoring and validation of pipeline performance
- Legacy system decommissioning
- Documentation and knowledge transfer

**Shared Layer Maintenance:**
- Establish shared layer maintenance procedures
- Create contribution guidelines for pipeline teams
- Set up automated testing for shared components

## Compliance & Standards

### Security Requirements
- All functions must use least-privilege IAM roles
- Sensitive data encrypted at rest and in transit
- VPC deployment for network isolation
- Regular security assessments and penetration testing

### Monitoring Requirements
- CloudWatch Logs for all function executions
- X-Ray tracing enabled for request flows
- Custom metrics for business KPIs
- Alerting for error rates and performance degradation

### Documentation Standards
- Each service must have comprehensive README
- API documentation using OpenAPI specifications
- Runbooks for operational procedures
- ADRs for significant architectural decisions

## Related Decisions

- **ADR-002**: Shared Layer Architecture and Component Standards (planned)
- **ADR-003**: DynamoDB single-table design patterns (planned)
- **ADR-004**: Event-driven communication patterns (planned)
- **ADR-005**: Contract validation and signing standards (planned)
- **ADR-006**: Monitoring and observability strategy (planned)
- **ADR-007**: Data migration strategy (planned)
- **ADR-008**: Pipeline deployment and versioning strategy (planned)

## References

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Serverless Application Lens](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/)
- [Moneta Core Brainstorming Framework](./brainstorming.md)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)

## Notes

- **Author**: System Architecture Team
- **Version**: 1.0
- **Reviewers**: Engineering Team, DevOps Team, Product Management
- **Next Review Date**: 2025-02-15

## Changelog

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-01-16 | Initial ADR proposal | Architecture Team |

---

## Architectural Pattern Visualization

### Current Architecture: Multi-Layered with Central Delegation

```mermaid
graph TD
    A[HTTP Request: api/v1/events] --> B[Rails Controller]
    B --> C[Event Validation Layer]
    C --> D[Event Delegation Service]
    
    D --> E[Subscription Charge Service]
    D --> F[Dispute Service]
    D --> G[Reconciliation Service]
    D --> H[Settlement Service]
    D --> I[Authentication Service]
    
    E --> J[Transportation Service]
    F --> J
    G --> J
    H --> J
    I --> J
    
    J --> K[Partner Delivery]
    
    L[(PostgreSQL DB 1)] --> E
    M[(PostgreSQL DB 2)] --> F
    N[(PostgreSQL DB 3)] --> G
    O[(PostgreSQL DB 4)] --> H
    P[(PostgreSQL DB 5)] --> I
    
    Q[Sidekiq Background Jobs] --> J
```

### Target Architecture: Pipeline-Oriented with Shared Layer

```mermaid
graph TD
    A1[HTTP: api/v1/events/subscription_charges] --> B1[Subscription Pipeline]
    A2[HTTP: api/v1/events/disputes] --> B2[Dispute Pipeline]
    A3[HTTP: api/v1/events/reconciliations] --> B3[Reconciliation Pipeline]
    A4[HTTP: api/v1/events/settlements] --> B4[Settlement Pipeline]
    A5[HTTP: api/v1/auth/*] --> B5[Auth Pipeline]
    
    B1 --> C1[Validate Contract]
    C1 --> D1[Process Business Logic]
    D1 --> E1[Sign Contract]
    E1 --> F1[Direct Partner Delivery]
    
    B2 --> C2[Validate Dispute Terms]
    C2 --> D2[Process Dispute Logic]
    D2 --> E2[Generate Response]
    E2 --> F2[Partner Notification]
    
    B3 --> C3[Validate Data]
    C3 --> D3[Matching Logic]
    D3 --> E3[Generate Report]
    E3 --> F3[Partner Response]
    
    B4 --> C4[Validate Settlement]
    C4 --> D4[Process Settlement]
    D4 --> E4[Generate Confirmation]
    E4 --> F4[Partner Settlement]
    
    B5 --> C5[OIDC Processing]
    C5 --> D5[Token Management]
    D5 --> E5[User Validation]
    E5 --> F5[Auth Response]
    
    subgraph SharedLayer["🔧 Shared Layer (Lambda Layer)"]
        SL1[Domain Models]
        SL2[Repository Layer]
        SL3[Business Services]
        SL4[Contract Validator]
        SL5[Event Processor]
        SL6[Contract Signing]
        SL7[Event Delivery]
    end
    
    SharedLayer -.-> B1
    SharedLayer -.-> B2
    SharedLayer -.-> B3
    SharedLayer -.-> B4
    SharedLayer -.-> B5
    
    G1[(DynamoDB: Subscriptions)] --> SL2
    G2[(DynamoDB: Disputes)] --> SL2
    G3[(DynamoDB: Reconciliations)] --> SL2
    G4[(DynamoDB: Settlements)] --> SL2
    G5[(DynamoDB: Users)] --> SL2
    
    H[EventBridge] --> SL5
    SL5 --> B1
    SL5 --> B2
    SL5 --> B3
    SL5 --> B4
    SL5 --> B5
```

---

**Decision Status**: This ADR requires review and approval from:
- [ ] Engineering Team Lead
- [ ] DevOps Team Lead  
- [ ] Product Manager
- [ ] Security Team
- [ ] CTO

**Approval Timeline**: 2 weeks from proposal date
**Implementation Start**: Upon approval + resource allocation
