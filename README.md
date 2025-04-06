# Discord Account Generator Bot 🤖

A powerful Discord bot for managing and distributing accounts with premium features, cooldowns, and comprehensive admin controls.

![Discord Bot](https://img.shields.io/badge/Discord-Bot-7289DA?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)

## ✨ Features

### Account Management
- Generate accounts with premium/free tiers
- Automatic stock management
- Bulk generation capabilities
- Support for multiple services
- Special handling for Ubisoft/Siege accounts

### User Management
- Premium subscription system
- Customizable cooldowns
- User blacklisting
- Detailed user statistics
- Role-based access control

### Admin Controls
- Add/remove stock
- Manage user subscriptions
- View detailed user information
- Service management
- Blacklist management

### Security
- Role-based permissions
- Channel restrictions
- Admin-only commands
- Customizable access levels

## 🚀 Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install discord.py
```

3. Configure `config.json`:
```json
{
    "token": "YOUR_DISCORD_TOKEN_HERE",
    "guild-id": "YOUR_GUILD_ID_HERE",
    "developer-server-id": "DEVELOPER_SERVER_ID",
    
    // ... other configuration options
}
```

## 📝 Configuration Guide

### Essential Settings
- `token`: Your Discord bot token
- `guild-id`: Main server ID
- `developer-server-id`: Development server ID
- `rotating-proxy`: Proxy configuration for API calls
- `siegeskins-api-key`: API key for Siege skins verification

### Channel & Role Configuration
- `gen-channels`: List of channel IDs where generation is allowed
- `admin-roles`: List of role IDs with admin permissions
- `roles`: Custom role configurations with cooldowns and permissions

### Feature Settings
- `stock-command-silent`: Toggle visibility of stock command
- `remove-capture-from-stock`: Auto-remove used accounts
- `commands-give-cooldown`: Enable command cooldowns
- `maximum-file-size`: Max file size for stock uploads (default: 2MB)

## 🛠️ Commands

### User Commands
- `/generate <service> [premium]` - Generate an account
- `/stock` - View available stock
- `/auth view` - View subscription status

### Admin Commands
- `/addstock <service> <file> [premium] [silent]` - Add stock
- `/bulkgen <service> <amount> <premium> [silent]` - Bulk generate accounts
- `/deleteservice <service> [premium]` - Delete a service
- `/blacklist <user> [status]` - Manage user blacklist
- `/setnote <user> <note>` - Add notes to users
- `/user <user>` - View user information

### Subscription Management
- `/auth add <user> <stage> <time>` - Add subscription time
- `/auth massadd <stage> <time>` - Mass add subscription time
- `/auth remove <user>` - Remove subscription
- `/cooldown set <user> <stage> <time>` - Set user cooldown
- `/cooldown reset <user> <stage>` - Reset user cooldown

## 🔒 Security Features

- Role-based access control
- Channel restrictions
- Subscription verification
- Blacklist system
- Custom cooldowns per role

## 📊 Stock Management

The bot supports multiple services with separate stock for:
- Free accounts
- Premium accounts
- Special handling for Ubisoft/Siege accounts

## ⚙️ Advanced Features

### Ubisoft Account Verification
- Automatic account validation
- Detailed account information retrieval
- Siege stats integration
- Platform linking verification

### Subscription System
- Multiple subscription tiers
- Time-based subscriptions
- Mass subscription management
- Custom cooldowns per tier

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This bot is for educational purposes only. Make sure to comply with all relevant terms of service and laws when using this bot.
