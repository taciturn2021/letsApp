This is going to be a chatApp that is sort of a whatsapp clone/messenger clone. it is a project for my advanced database course, it will have the following features: (Note this is only the backend )
- Backend using flask in python
- Database MongoDB
- Message sending / receiving between different users.
- Group chats
- Emojis sending and receving in messages.
- File sending and receving in messages.
- User profiles with authentication that includes salting and hashing the password.
- ensure the following for the mongodb setup:
Must have atleast 10 entities in terms of normal ERD setup (of course itll get reduced when converted to collections)
- Query Optimization
- Creating indexes
- Creating pipelines

Message Status Tracking

Sent/delivered/read receipts
This is a core feature of modern messaging apps that improves user experience
Database Sharding Strategy

Define how you'll partition data for scalability
Important for a database course to demonstrate understanding of handling large datasets
Caching Implementation

Redis/MongoDB caching for frequent queries
Improves performance for active conversations and user data
Message Search Functionality

Text indexing for searching message content
Shows advanced MongoDB query capabilities
Analytics and Metrics

Track message volumes, active users, etc.
Demonstrates aggregation pipeline usage for reporting
Rate Limiting and Security Measures

Prevent abuse and protect against brute force attacks
Demonstrates responsible API design

Data Validation and Sanitization

Input validation to prevent injection attacks
Output sanitization to ensure consistent data
Backup and Recovery Procedures

Document how data would be backed up
Important for database management
Typing Indicators

Show when users are composing messages
Requires WebSocket implementation
Presence System (Online/Offline Status)

Track and broadcast user availability
Demonstrates real-time updates using MongoDB change streams
API Documentation

Swagger/OpenAPI documentation
Important for any backend project
Message Pagination

Load messages in chunks for better performance
Demonstrates cursor-based pagination with MongoDB