# Introduction
This document outlines the technical design and architecture for the core mPass (digital passport) management features within the Moneta Network. The proposed solution leverages AWS Serverless Application Model (SAM) with Amazon DynamoDB as the primary data store and Amazon Cognito for user identity management. This design prioritizes security, scalability, and atomicity for all mPass lifecycle operations.

The following sections detail the API endpoints, data flows, and backend logic for issuing, activating, locking, and destroying mPasses.

# System Components & Data Models
## Core Components
Moneta Core API: A set of serverless functions (AWS Lambda) exposed via Amazon API Gateway, responsible for handling all mPass management requests.

Amazon DynamoDB: NoSQL database for storing mPasses, mPassPublicKeys, and MoCounters data.

Amazon Cognito: Manages user identities, providing a unique user_id which serves as the mPassID.

Amazon EventBridge: A serverless event bus used to decouple services and broadcast mPass lifecycle events.

Amazon SQS (Simple Queue Service): Used to decouple the batch request intake from the individual mPass creation process, ensuring resilient and scalable processing.

## DynamoDB Table: mPasses
The mPasses table is central to this design.

 

- Partition Key: mPassID (String, UUIDv4 from Cognito user_id)
- GSI 1 (mPassNumber-index):
    - PK: mPassNumber
- GSI 2 (moID-mPassNumber-index):
    - PK: moID
    - SK: mPassNumber
- Attributes:
    - externalUserID: (String) The MO's internal user ID.
    - moID: (String) The UUID of the issuing Membership Organization.
    - status: (String) PENDING, ACTIVE, USER_LOCKED, ADMIN_LOCKED, MO_LOCKED, EXPIRED, DESTROYED.
    - activateToken: (String) A secure, random token for the activation step.
    - activateExpireAt: (Number) Unix timestamp for activation token expiry.
    - tier: (String) e.g., "Standard", "Platinum".
    - activePublicKeyID: (String) UUIDv4, FK to mPassPublicKeys table.
    - createdAt: (Number) Unix timestamp.
    - updatedAt: (Number) Unix timestamp.
    - expiresAt: (Number) Unix timestamp.
    - metadata: (Map) JSON blob for additional details.

2.3. DynamoDB Table: mPassPublicKeys
Partition Key: publicKeyID (String, UUIDv4)

Attributes:

mPassID: (String) FK to the mPasses table.

publicKey: (String) The public key provided during activation.

algorithm: (String) The encryption algorithm used (e.g., RSA-2048).

createdAt: (Number) Unix timestamp.

expiresAt: (Number) Unix timestamp.

2.4. DynamoDB Table: MoCounters
This table manages the auto-incrementing account number for each Membership Organization to ensure uniqueness and atomicity.

Partition Key: moID (String)

Attributes:

moID: (String) The UUID of the Membership Organization.

lastAccountNumber: (Number) The last successfully assigned account number for the MO.

3. mPass Management Features
3.1. mPass Issuance Process (Single)
This process creates a new, inactive mPass and a corresponding user identity in Cognito.

API Endpoint: POST /mo/v1/mPass/request

Request Header:

mo-id: <mo_id_uuid>

Request Payload:
{
  "mo_user_id": "user-id-from-mo-system-123",
  "tier": "Gold",
  "status": "PENDING",
  "metadata": { "key": "value" },
  "expiresAt": 1798752000
}


Process Flow:

Authorization: The API Gateway authorizer validates the MO's credentials and permissions. The mo_id is extracted from the request context.

Check for Duplicates: The Lambda function queries the mPasses table using the moID-mPassNumber-index to check if an mPass already exists for the given mo_id and mo_user_id. If a record is found, it returns a 409 Conflict error.

Generate Unique mPassNumber: This is a multi-step, atomic process.

a. Retrieve MO's IIN: Fetch the MO's details, including their assigned 5-digit Issuer Identification Number (IIN), from a configuration store or table using the moID.

b. Atomically Generate Account Identifier: The core of the generation logic relies on a DynamoDB atomic counter. The Lambda function executes a single UpdateItem operation on the MoCounters table.

Operation: UpdateItem

Key: { "moID": "<current_mo_id>" }

UpdateExpression: SET lastAccountNumber = if_not_exists(lastAccountNumber, :start) + :incr

ExpressionAttributeValues: { ":start": 0, ":incr": 1 }

ReturnValues: UPDATED_NEW
This atomic operation increments the counter for the specific MO and returns the newly incremented number. DynamoDB guarantees that even with highly concurrent requests, each will receive a unique, sequential number.

c. Assemble Final mPassNumber:

The number returned from the UpdateItem call is the Account Identifier. It is padded with leading zeros to a length of 9 digits (e.g., 123 becomes 000000123).

The 15-digit base number is assembled: '4' (MII) + IIN + Padded Account Identifier.

A Check Digit is calculated on the 15-digit base using the Luhn algorithm to form the final 16th digit.

Create Cognito User:

The Moneta Core service calls Amazon Cognito's AdminCreateUser API.

The username for the Cognito user will be the newly generated 16-digit mPassNumber.

The user_id returned by Cognito becomes the mPassID.

Create mPass Record: An item is created in the mPasses table with the details from the request payload, the generated mPassNumber, and the mPassID.

Generate Activation Token: A cryptographically secure random string is generated for activateToken. activateExpireAt is set based on MO configuration (e.g., 24 hours from creation).

Publish Event: A mPass.Created event is published to Amazon EventBridge with the mPass details.

Return Response: The API returns a 201 Created response to the MO.

Response Payload (201 Created):
{
  "mPassID": "cognito-generated-uuid-v4",
  "mPassNumber": "4123450000001239",
  "status": "PENDING",
  "activateToken": "secure-random-token",
  "activateExpireAt": 1767225600,
  "expiresAt": 1798752000
}


Flow Diagram:




sequenceDiagram
    participant MO as Membership Org
    participant APIGW as API Gateway
    participant Lambda as Moneta Core (Lambda)
    participant DynamoDB
    participant Cognito
    participant EventBridge
    MO->>APIGW: POST /mo/v1/mPass/request
    APIGW->>Lambda: Invoke Function
    Lambda->>DynamoDB: Query for existing mo_user_id on mPasses table
    DynamoDB-->>Lambda: Result (Not Found)
    Lambda->>DynamoDB: UpdateItem on MoCounters table (Atomic Increment)
    DynamoDB-->>Lambda: New Account Identifier
    Lambda->>Cognito: AdminCreateUser (username=mPassNumber)
    Cognito-->>Lambda: User created (returns user_id as mPassID)
    Lambda->>DynamoDB: Create mPass item
    DynamoDB-->>Lambda: Confirmation
    Lambda->>Lambda: Generate activateToken
    Lambda->>EventBridge: Publish mPass.Created event
    Lambda-->>APIGW: Return 201 Created
    APIGW-->>MO: Response
3.2. mPass Issuance Process (Batch)
This process allows an MO to request the creation of multiple mPasses in a single API call. The processing is handled asynchronously to provide a fast API response and ensure reliable creation of each mPass.



API Endpoint: POST /mo/v1/mPass/multipleRequest
Request Header:
mo-id: <mo_id_uuid>
Request Payload: An array of mPass request objects.
{
  "requests": [
    { "mo_user_id": "user-a-111", "tier": "Gold", "metadata": {} },
    { "mo_user_id": "user-b-222", "tier": "Standard", "metadata": {} },
    { "mo_user_id": "user-c-333", "tier": "Gold", "expiresAt": 1798752000 }
  ]
}



Process Flow (Asynchronous):

Intake & Validation (API Lambda):

A dedicated Lambda function handles the multipleRequest endpoint.

It performs initial validation on the request payload (e.g., checks if the array is not empty, limits the batch size to a reasonable number like 500).

For each item in the requests array, it adds the mo_id from the header.

It sends each individual mPass request object as a separate message to an Amazon SQS queue.

The API immediately returns a 202 Accepted response to the MO, indicating the batch request has been received and is being processed.

Worker Processing (Worker Lambda):

A second "worker" Lambda function is configured with the SQS queue as its event source.

This Lambda will be invoked in batches with messages from the queue.

For each message (representing one mPass to create), the worker Lambda executes the exact same logic as the single mPass issuance process (Section 3.1, steps 2-7): check for duplicates, generate mPassNumber, create Cognito user, create DynamoDB record, and publish the mPass.Created event.

This isolates the creation logic, making it reusable and easier to maintain. Errors in processing one message (e.g., a duplicate mo_user_id) will not halt the processing of other messages in the batch. SQS will handle retries for failed messages automatically.

Response Payload (202 Accepted):
{
  "status": "Processing",
  "message": "Your batch request of 3 items has been accepted and is being processed.",
  "batchId": "a-unique-batch-identifier"
}


Flow Diagram:




sequenceDiagram
    participant MO as Membership Org
    participant APIGW as API Gateway
    participant IntakeLambda as Intake Lambda
    participant SQS
    participant WorkerLambda as Worker Lambda
    participant Services as (DynamoDB, Cognito, EventBridge)
    MO->>APIGW: POST /mo/v1/mPass/multipleRequest
    APIGW->>IntakeLambda: Invoke Function with batch payload
    loop For each request in payload
        IntakeLambda->>SQS: SendMessage(mPass request details)
    end
    IntakeLambda-->>APIGW: Return 202 Accepted
    APIGW-->>MO: Response
    Note right of SQS: SQS triggers Worker Lambda
    SQS->>WorkerLambda: Invoke with batch of messages
    loop For each message
        WorkerLambda->>Services: Execute Single mPass Creation Logic
    end
3.3. mPass Activation Process
This process activates a PENDING mPass.



API Endpoint: POST /mo/v1/mPass/{mPassID}/activate
Request Payload:
{
  "activateToken": "secure-random-token",
  "public_key": "...",
  "algorithm": "RSA-2048",
  "expires_at": 1828224000
}



Process Flow:

Fetch mPass: Retrieve the mPass from DynamoDB using the mPassID.

Validation:

Verify the mPass status is PENDING. If not, return 409 Conflict.

Check that the provided activateToken matches the one stored and has not expired. If not, return 401 Unauthorized.

Manage Public Key (Optional):

If public_key is present in the payload, a new item is created in the mPassPublicKeys table.

The mPasses table item is updated, setting the activePublicKeyID to the ID of the new public key record.

Update mPass Status: The status of the mPass is updated from PENDING to ACTIVE. The activateToken and activateExpireAt fields are cleared.

Publish Event: A mPass.Activated event is published to EventBridge.

Return Response: The API returns a 200 OK with the updated mPass details.

Flow Diagram:




sequenceDiagram
    participant MO as Membership Org
    participant APIGW as API Gateway
    participant Lambda as Moneta Core (Lambda)
    participant DynamoDB
    participant EventBridge
    MO->>APIGW: POST /mo/v1/mPass/{mPassID}/activate
    APIGW->>Lambda: Invoke Function
    Lambda->>DynamoDB: Get mPass by mPassID
    DynamoDB-->>Lambda: mPass data (status=PENDING, activateToken)
    Lambda->>Lambda: Validate status and activateToken
    alt public_key provided
        Lambda->>DynamoDB: Create mPassPublicKeys item
        DynamoDB-->>Lambda: publicKeyID
        Lambda->>DynamoDB: Update mPass with activePublicKeyID
    end
    Lambda->>DynamoDB: Update mPass status to ACTIVE & clear token
    Lambda->>EventBridge: Publish mPass.Activated event
    Lambda-->>APIGW: Return 200 OK
    APIGW-->>MO: Response
3.4. mPass Lock Processes
3.4.1. User-Initiated Lock
API Endpoint: POST /mo/v1/mPass/{mPassID}/userLock

Process Flow:

Fetch the mPass and verify its status is ACTIVE. If not, return 409 Conflict.

Update the mPass status in DynamoDB to USER_LOCKED.

Call Cognito's AdminDisableUser API to deactivate the user account.

Call Cognito's AdminUserGlobalSignOut API to revoke all active refresh and access tokens.

Publish a mPass.UserLocked event to EventBridge.

Return a 200 OK response.

3.4.2. MO-Initiated Lock
API Endpoint: POST /mo/v1/mPass/{mPassID}/moLock

Process Flow:

Fetch the mPass and verify its status is ACTIVE. If not, return 409 Conflict.

Update the mPass status in DynamoDB to MO_LOCKED.

Call Cognito's AdminDisableUser API to deactivate the user account.

Call Cognito's AdminUserGlobalSignOut API to revoke all active refresh and access tokens.

Publish a mPass.MoLocked event to EventBridge.

Return a 200 OK response.

3.4.3. Lock Flow Diagram


sequenceDiagram
    participant Requester as MO or User App
    participant APIGW as API Gateway
    participant Lambda as Moneta Core (Lambda)
    participant DynamoDB
    participant Cognito
    participant EventBridge
    Requester->>APIGW: POST /mo/v1/mPass/{mPassID}/[userLock | moLock]
    APIGW->>Lambda: Invoke Function
    Lambda->>DynamoDB: Get mPass by mPassID
    DynamoDB-->>Lambda: mPass data (status=ACTIVE)
    Lambda->>Lambda: Validate status is ACTIVE
    Lambda->>DynamoDB: Update mPass status to [USER_LOCKED | MO_LOCKED]
    Lambda->>Cognito: AdminDisableUser
    Cognito-->>Lambda: Success
    Lambda->>Cognito: AdminUserGlobalSignOut
    Cognito-->>Lambda: Success
    Lambda->>EventBridge: Publish mPass.[UserLocked | MoLocked] event
    Lambda-->>APIGW: Return 200 OK
    APIGW-->>Requester: Response
 

3.5. mPass Destruction Process
This is a privileged, hard-delete operation for administrative use only.

API Endpoint: POST /admin/v1/mPass/{mPassID}/destroy

Process Flow:

Authorization: This endpoint must be protected by a strict IAM policy allowing access only to Moneta Core administrators.

Delete Cognito User: Call Cognito's AdminDeleteUser API to permanently remove the user from the user pool.

Delete mPass Record: Delete the item from the mPasses table in DynamoDB.

Delete Public Keys: Query the mPassPublicKeys table for all keys associated with the mPassID and perform a batch delete operation.

Publish Event: A mPass.Destroyed event is published to EventBridge.

Return Response: Return a 204 No Content response upon successful completion.

Flow Diagram:



```
sequenceDiagram
    participant Admin as Moneta Admin
    participant APIGW as API Gateway
    participant Lambda as Moneta Core (Lambda)
    participant DynamoDB
    participant Cognito
    participant EventBridge
    Admin->>APIGW: POST /admin/v1/mPass/{mPassID}/destroy
    APIGW->>Lambda: Invoke Function (with IAM auth)
    Lambda->>Cognito: AdminDeleteUser
    Cognito-->>Lambda: Success
    Lambda->>DynamoDB: Delete mPass item
    DynamoDB-->>Lambda: Success
    Lambda->>DynamoDB: Query and Batch Delete mPassPublicKeys items
    DynamoDB-->>Lambda: Success
    Lambda->>EventBridge: Publish mPass.Destroyed event
    Lambda-->>APIGW: Return 204 No Content
    APIGW-->>Admin: Response
```