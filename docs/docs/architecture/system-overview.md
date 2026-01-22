---
sidebar_position: 1
---

# System Architecture Overview

HackAgent is built as a comprehensive security testing platform with a modern, scalable architecture designed to handle enterprise-grade AI agent vulnerability assessments.

## 🏗️ High-Level Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[React Dashboard]
        DOCS[Docusaurus Documentation]
    end
    
    subgraph "API Gateway"
        API[Django REST Framework]
        AUTH[Authentication Layer]
        RATE[Rate Limiting]
    end
    
    subgraph "Core Services"
        AGENT[Agent Management]
        ATTACK[⚔️ Attack Engine]
        EVAL[Evaluation Service]
        BILLING[Billing Service]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL)]
        CACHE[(Redis Cache)]
        FILES[File Storage]
        DATASETS[📊 Datasets]
    end
    
    subgraph "External Integrations"
        ADK[🔌 Google ADK]
        OPENAI[🔌 OpenAI SDK]
        LITELLM[LiteLLM]
        CUSTOM[Custom Agents]
    end
    
    UI --> API
    DOCS --> API
    API --> AUTH
    API --> RATE
    API --> AGENT
    API --> ATTACK
    API --> EVAL
    API --> BILLING
    
    AGENT --> DB
    ATTACK --> DB
    ATTACK --> DATASETS
    EVAL --> DB
    BILLING --> DB
    
    ATTACK --> CACHE
    EVAL --> CACHE
    
    AGENT --> ADK
    AGENT --> OPENAI
    AGENT --> LITELLM
    AGENT --> CUSTOM
    
    EVAL --> FILES

    style ATTACK fill:#ff6b6b,stroke:#c92a2a,color:#fff
    style DATASETS fill:#4dabf7,stroke:#1971c2,color:#fff
    style ADK fill:#69db7c,stroke:#2f9e44,color:#fff
    style OPENAI fill:#69db7c,stroke:#2f9e44,color:#fff
```

### 🔗 Explore Components

import Link from '@docusaurus/Link';

<div className="row" style={{marginTop: '1rem'}}>
  <div className="col col--3" style={{marginBottom: '1rem'}}>
    <Link to="/attacks/" style={{textDecoration: 'none', display: 'block', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)'}}>
      <h4 style={{margin: 0}}>⚔️ Attack Engine</h4>
      <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>Learn about different attack types and techniques</p>
    </Link>
  </div>
  <div className="col col--3" style={{marginBottom: '1rem'}}>
    <Link to="/datasets/" style={{textDecoration: 'none', display: 'block', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)'}}>
      <h4 style={{margin: 0}}>📊 Datasets</h4>
      <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>Configure data sources for security testing</p>
    </Link>
  </div>
  <div className="col col--3" style={{marginBottom: '1rem'}}>
    <Link to="/integrations/google-adk" style={{textDecoration: 'none', display: 'block', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)'}}>
      <h4 style={{margin: 0}}>🔌 Google ADK</h4>
      <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>Test Google ADK-based agents</p>
    </Link>
  </div>
  <div className="col col--3" style={{marginBottom: '1rem'}}>
    <Link to="/integrations/openai-sdk" style={{textDecoration: 'none', display: 'block', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)'}}>
      <h4 style={{margin: 0}}>🔌 OpenAI SDK</h4>
      <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>Test OpenAI SDK-based agents</p>
    </Link>
  </div>
</div>
    style ADK fill:#69db7c,stroke:#2f9e44,color:#fff
    style OPENAI fill:#69db7c,stroke:#2f9e44,color:#fff
```

## 🧩 Core Components

### Frontend Layer

**React Dashboard (`/frontend/dashboard/`)**
- **Technology**: Next.js 15+ with React 19
- **UI Framework**: TailwindCSS + shadcn/ui components
- **Authentication**: Privy integration (Web3 + Social login)
- **State Management**: React hooks with local state
- **API Client**: Auto-generated TypeScript client from OpenAPI

**Docusaurus Documentation (`/frontend/docs/`)**
- **Purpose**: Comprehensive user and developer documentation
- **Features**: Search, versioning, mobile-responsive
- **Integration**: Served alongside the main application

### API Gateway

**Django REST Framework**
- **Routing**: RESTful endpoints with OpenAPI documentation
- **Serialization**: Automatic data validation and transformation
- **Pagination**: Consistent pagination across all endpoints
- **Filtering**: Django-filter integration for complex queries

**Authentication Layer**
- **Privy Authentication**: JWT-based auth with Web3/social login
- **API Key Authentication**: For programmatic access
- **Multi-tenant Support**: Organization-based access control
- **Permission System**: Role-based permissions

### Core Services

**Agent Management Service**
- **Purpose**: Manage AI agent configurations and connections
- **Features**: Multi-framework support, health checking, metadata management
- **Supported Types**: Google ADK, OpenAI SDK, LiteLLM, Custom REST APIs

**Attack Engine**
- **Attack Types**: Prompt injection, jailbreaking, goal hijacking
- **Techniques**: AdvPrefix, indirect injection, filter evasion
- **Execution**: Async attack orchestration with result aggregation
- **Extensibility**: Plugin system for custom attack vectors

**Evaluation Service**
- **Judge Models**: AI-powered result evaluation
- **Scoring**: Vulnerability severity assessment
- **Metrics**: Success rates, confidence scores, risk ratings
- **Reporting**: Detailed analysis and recommendations

**Billing Service**
- **Credit System**: Usage-based billing with real-time tracking
- **Payment Processing**: Stripe integration for subscriptions
- **Usage Logging**: Detailed API usage and cost tracking
- **Limits**: Rate limiting and quota management

### Data Layer

**PostgreSQL Database**
- **Multi-tenancy**: Organization-based data isolation
- **Models**: Agents, Attacks, Runs, Results, Traces, Users
- **Relationships**: Complex foreign key relationships with cascade handling
- **Performance**: Optimized queries with proper indexing

**Redis Cache (Future)**
- **Session Storage**: User session management
- **Attack Results**: Temporary result caching
- **Rate Limiting**: Token bucket implementation

## 🔄 Data Flow Architecture

### Attack Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Dashboard
    participant API
    participant AttackEngine
    participant Agent
    participant Evaluator
    participant Database

    User->>Dashboard: Configure Attack
    Dashboard->>API: POST /api/attack
    API->>Database: Store Attack Config
    API->>AttackEngine: Execute Attack
    
    loop For Each Attack Vector
        AttackEngine->>Agent: Send Test Prompt
        Agent->>AttackEngine: Return Response
        AttackEngine->>Evaluator: Evaluate Response
        Evaluator->>AttackEngine: Return Assessment
        AttackEngine->>Database: Store Result
    end
    
    AttackEngine->>API: Attack Complete
    API->>Dashboard: Results Available
    Dashboard->>User: Display Results
```

### Multi-Tenant Data Access

```mermaid
graph TB
    subgraph "Organization A"
        USER_A[User A]
        AGENT_A[Agents A]
        ATTACK_A[Attacks A]
        RUN_A[Runs A]
    end
    
    subgraph "Organization B"
        USER_B[User B]
        AGENT_B[Agents B]
        ATTACK_B[Attacks B]
        RUN_B[Runs B]
    end
    
    subgraph "Shared Infrastructure"
        API[API Layer]
        DB[(Database)]
    end
    
    USER_A --> API
    USER_B --> API
    API --> DB
    
    DB --> AGENT_A
    DB --> ATTACK_A
    DB --> RUN_A
    
    DB --> AGENT_B
    DB --> ATTACK_B
    DB --> RUN_B
```

## 🔐 Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Privy
    participant API
    participant Database

    User->>Frontend: Login Request
    Frontend->>Privy: Authenticate
    Privy->>Frontend: JWT Token
    Frontend->>API: Request with JWT
    API->>Privy: Validate Token
    Privy->>API: Token Valid
    API->>Database: Query User Data
    Database->>API: User Profile
    API->>Frontend: Authorized Response
```

### Data Protection

- **Encryption at Rest**: Database encryption for sensitive data
- **Encryption in Transit**: TLS 1.3 for all API communications
- **Access Control**: Row-level security based on organization membership
- **Audit Logging**: Comprehensive audit trails for all actions
- **Data Isolation**: Strict tenant data separation

## 📈 Scalability Considerations

### Horizontal Scaling

- **Stateless API**: No server-side session storage
- **Database Optimization**: Read replicas for query scaling
- **Caching Strategy**: Redis for session and result caching
- **Load Balancing**: Multiple API server instances

### Performance Optimization

- **Async Processing**: Non-blocking attack execution
- **Result Streaming**: Real-time result updates via WebSockets
- **Database Indexing**: Optimized queries for large datasets
- **CDN Integration**: Static asset delivery optimization

## 🧪 Testing Architecture

### Test Isolation

```mermaid
graph TB
    subgraph "Test Environment"
        TEST_DB[(Test Database)]
        MOCK_AGENTS[Mock AI Agents]
        TEST_API[API Test Server]
    end
    
    subgraph "Testing Tools"
        PYTEST[Pytest Framework]
        FACTORY[Factory Boy]
        FIXTURES[Test Fixtures]
    end
    
    PYTEST --> TEST_API
    PYTEST --> TEST_DB
    PYTEST --> MOCK_AGENTS
    FACTORY --> FIXTURES
    FIXTURES --> TEST_DB
```

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: API endpoint testing
- **End-to-End Tests**: Full user workflow testing
- **Security Tests**: Vulnerability scanning and penetration testing
- **Performance Tests**: Load testing and benchmarking

## 🚀 Deployment Architecture

### Container Strategy

```yaml
services:
  web:
    image: hackagent:latest
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL
      - REDIS_URL
      - PRIVY_APP_ID
    
  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  redis:
    image: redis:7-alpine
    
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### Production Considerations

- **Environment Separation**: Development, staging, production environments
- **Secret Management**: Environment-based secret injection
- **Health Checks**: Application and database health monitoring
- **Backup Strategy**: Automated database backups and restoration
- **Monitoring**: Application performance monitoring (APM)

This architecture provides a robust, scalable foundation for comprehensive AI agent security testing while maintaining security, performance, and maintainability standards. 