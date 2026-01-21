# MedSync Platform Infrastructure Diagram

## High-Level Architecture

```
[Users] --> [CloudFront CDN] --> [API Gateway] --> [Load Balancer]
                                                         |
                                    +--------------------+--------------------+
                                    |                    |                    |
                              [User Service]      [Patient Service]   [Notifications Service]
                                    |                    |                    |
                              [PostgreSQL]          [PostgreSQL]         [MongoDB]
```

## Components

- **CloudFront CDN:** Delivers static assets (JS, CSS, images) with low latency.
- **API Gateway:** Manages API traffic, authentication, and rate limiting.
- **Load Balancer:** Distributes traffic across multiple instances of each service.
- **Microservices:** Each service is independently deployable and scalable.
- **Databases:** PostgreSQL for relational data, MongoDB for flexible document storage.
