# LetsApp Backend

A comprehensive real-time chat application backend built with Flask, featuring AI-powered conversations, group messaging, voice/video calls, and secure file sharing.

## ✨ Features

### Core Messaging

- **Real-time Chat**: Instant messaging with WebSocket support
- **Group Messaging**: Create and manage group conversations
- **Message Encryption**: End-to-end encryption for secure communication
- **File Sharing**: Support for images, videos, documents, and other media
- **Message Status**: Read receipts and delivery confirmations

### AI Integration

- **Leta AI Assistant**: Built-in AI chat powered by Google Gemini
- **Conversation Context**: AI maintains context from previous messages
- **Chat History**: Persistent AI conversation history with pagination
- **Personalized Responses**: AI tailored to user preferences

### Communication Features

- **Voice & Video Calls**: Real-time calling with WebRTC
- **Presence System**: Online/offline status and typing indicators
- **Contact Management**: Add and manage contacts
- **User Profiles**: Customizable user profiles with avatars

### Security & Authentication

- **JWT Authentication**: Secure token-based authentication
- **Password Encryption**: Bcrypt password hashing
- **API Key Management**: Secure storage of user API keys
- **Rate Limiting**: Protection against spam and abuse

## 🛠️ Technology Stack

- **Backend Framework**: Flask 2.3+
- **Database**: MongoDB with PyMongo
- **Real-time**: Flask-SocketIO with EventLet
- **Authentication**: JWT (JSON Web Tokens)
- **AI Service**: Google Gemini API
- **File Storage**: Local file system with organized structure
- **Encryption**: AES encryption for sensitive data

## 📋 Prerequisites

- Python 3.8 or higher
- MongoDB instance (local or cloud)
- Google Gemini API key (for AI features)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd letsApp
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```env
# Database
MONGO_URI=mongodb://localhost:27017/letsapp

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-here
JWT_ACCESS_TOKEN_EXPIRES=7200

# Server Configuration
FLASK_ENV=development
FLASK_DEBUG=True
PORT=5001

# File Upload Configuration
MAX_CONTENT_LENGTH=16777216
UPLOAD_FOLDER=instance/uploads

# AI Configuration (Optional - users can set their own)
GEMINI_API_KEY=your-gemini-api-key-here

# Encryption (Generate secure keys)
ENCRYPTION_KEY=your-32-byte-encryption-key-here
```

### 3. Initialize Database

Ensure MongoDB is running, then start the application:

```bash
python run.py
```

The application will automatically create necessary database collections.

### 4. Access the API

- **Base URL**: `http://localhost:5001`
- **API Documentation**: Available via the endpoints below
- **Health Check**: `GET /ping`

## 📚 API Endpoints

### Authentication

- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `GET /auth/verify` - Verify JWT token

### User Management

- `GET /api/users/profile` - Get user profile
- `PUT /api/users/profile` - Update user profile
- `POST /api/users/profile-picture` - Upload profile picture
- `PUT /api/users/{user_id}/api-key` - Set AI API key

### Messaging

- `GET /api/messages` - Get user messages
- `POST /api/messages` - Send message
- `PUT /api/messages/{message_id}` - Update message
- `DELETE /api/messages/{message_id}` - Delete message

### Group Management

- `POST /api/groups` - Create group
- `GET /api/groups` - Get user groups
- `PUT /api/groups/{group_id}` - Update group
- `POST /api/groups/{group_id}/members` - Add members
- `DELETE /api/groups/{group_id}/members/{user_id}` - Remove member

### AI Chat

- `POST /api/chat/ai/send` - Send message to AI
- `GET /api/chat/ai/history/{user_id}` - Get AI chat history
- `DELETE /api/chat/ai/history/{user_id}` - Clear AI chat history

### Calls

- `POST /api/calls/initiate` - Start voice/video call
- `POST /api/calls/{call_id}/answer` - Answer call
- `POST /api/calls/{call_id}/end` - End call

### File Management

- `POST /api/media/upload` - Upload file
- `GET /api/media/{file_id}` - Download file
- `DELETE /api/media/{file_id}` - Delete file

## 🔧 Configuration

### MongoDB Collections

The application uses the following MongoDB collections:

- `users` - User accounts and profiles
- `messages` - Chat messages
- `groups` - Group information
- `group_messages` - Group chat messages
- `ai_chat_messages` - AI conversation history
- `calls` - Call records
- `media_files` - File metadata
- `contacts` - User contacts

### File Storage Structure

```
instance/
├── uploads/
│   ├── profile_pictures/
│   ├── group_icons/
│   ├── chat_media/
│   └── documents/
```

### Security Features

- **Password Hashing**: Bcrypt with salt rounds
- **JWT Tokens**: Configurable expiration times
- **File Validation**: MIME type checking and size limits
- **Rate Limiting**: Per-endpoint and per-user limits
- **Input Validation**: Pydantic and Marshmallow schemas

## 🤖 AI Features

### Leta AI Assistant

The built-in AI assistant provides:

- **Natural Conversations**: Context-aware responses
- **Persistent History**: Conversation memory across sessions
- **Personalized Experience**: Tailored to user preferences
- **Multiple Capabilities**: Q&A, creative tasks, code help, and more

### AI Configuration

Users can set their own Gemini API keys for personalized AI experiences:

1. Get a Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Set it in user profile settings
3. Start chatting with Leta AI

## 🧪 Testing

### Running Tests

```bash
# Basic connectivity test
python test_ai_chat.py

# Check server status
curl http://localhost:5001/ping
```

### Manual Testing

1. **Authentication Flow**:

   - Register a new user
   - Login and receive JWT token
   - Use token for authenticated requests

2. **Messaging Test**:

   - Send messages between users
   - Test group messaging
   - Verify real-time delivery

3. **AI Chat Test**:
   - Set Gemini API key
   - Send messages to AI
   - Check conversation history

## 🐛 Troubleshooting

### Common Issues

**Database Connection Error**:

```
Error: ServerSelectionTimeoutError
Solution: Check MongoDB is running and MONGO_URI is correct
```

**JWT Token Invalid**:

```
Error: Invalid or expired token
Solution: Login again to get new token
```

**AI Chat Not Working**:

```
Error: API key not found
Solution: Set Gemini API key in user profile
```

**File Upload Failed**:

```
Error: File too large
Solution: Check MAX_CONTENT_LENGTH setting
```

### Debug Mode

Enable debug logging by setting:

```env
FLASK_DEBUG=True
FLASK_ENV=development
```

## 🔒 Security Considerations

### Production Deployment

For production deployment:

1. **Environment Variables**:

   - Use strong, unique secrets
   - Never commit .env files
   - Use environment-specific configurations

2. **Database Security**:

   - Enable MongoDB authentication
   - Use SSL/TLS connections
   - Implement proper network security

3. **API Security**:

   - Use HTTPS in production
   - Implement proper CORS policies
   - Set up rate limiting
   - Monitor for unusual activity

4. **File Security**:
   - Validate all uploaded files
   - Use virus scanning if needed
   - Implement proper access controls

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write descriptive commit messages
- Add tests for new features
- Update documentation as needed

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter any issues or have questions:

1. Check the troubleshooting section above
2. Search existing issues on GitHub
3. Create a new issue with detailed information
4. Include error messages and steps to reproduce

## 🚧 Roadmap

### Upcoming Features

- [ ] Message reactions and emoji support
- [ ] Advanced group permissions
- [ ] Message scheduling
- [ ] Custom AI personalities
- [ ] Voice message transcription
- [ ] Advanced search functionality
- [ ] Integration with external services
- [ ] Mobile push notifications

---

**LetsApp Backend** - Building the future of communication, one message at a time. 🚀
