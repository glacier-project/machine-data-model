# Message Template

## General Message Structure
```json
{
  "id": "uuid",
  "sender": "sender",
  "target": "target",
  "message_type": "Request", // or "Response" or "Event"
  "message": "$message_type"
}
```

## Message Types
```json
$message_type= {
  "header": {
    // The header of the message contains metadata about the message.
    "version": "1.0.0",
    // The version of the message format.
    "namespace": "Variable", 
    // E.g., Variable, Method, etc.
    "name": "Read", 
    // This field specifies the type of message. This field in combination with
    // the namespace field should uniquely identify the type of the message 
    // contained in the body/payload.
    // E.g., for a Request message, the name could be something like 
    // "Read", "Write", "Subscribe", etc.
  },
  "body": {
      // The body of the message contains the actual message content.
      // The content of the body depends on the type of message.
  }
}
```
### Read Request
```json
{
  "header": {
    "version": "1.0.0",
    "namespace": "Variable",
    "name": "Read"
  },
  "body": {
    "nodeId": "uuid"
    // or "nodePath": "path/to/node"
  }
}
```

### Read Response
```json
{
  "header": {
    "version": "1.0.0",
    "namespace": "Variable",
    "name": "Read"
  },
  "body": {
    "nodeId": "uuid",
    "value": "value",
    "timestamp": "timestamp"
  }
}
```
### Read Error Response
```json
{
  "header": {
    "version": "1.0.0",
    "namespace": "Variable",
    "name": "Read"
  },
  "body": {
    "error": "error",
    "description": "error description"
    // also errors should be well defined
  }
}
```

### Write Request
```json
{
  "header": {
    "version": "1.0.0",
    "namespace": "Variable",
    "name": "Write"
  },
  "body": {
    "nodeId": "uuid",
    // or "nodePath": "path/to/node"
    "value": "value"
  }
}
```

### Write Response
```json
{
  "header": {
    "version": "1.0.0",
    "namespace": "Variable",
    "name": "Write"
  },
  "body": {
    "result": "result"
  }
}
```

....