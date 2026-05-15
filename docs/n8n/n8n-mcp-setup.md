# n8n-MCP Setup Guide

## ✅ Installation Complete

n8n-MCP has been successfully added to your Cursor MCP configuration at `~/.cursor/mcp.json`.

## 🔄 Next Steps

1. **Restart Cursor** to load the new MCP server
2. The n8n-mcp tools will be available immediately with basic node documentation access

## 🎯 What You Can Do Now

With n8n-mcp configured, you can:

- **Search n8n nodes**: Find nodes by keyword, type, or capability
- **Get node documentation**: Detailed information about any n8n node
- **Validate configurations**: Check node and workflow configurations
- **Search templates**: Access 2,352 pre-built workflow templates
- **Build workflows**: Get AI assistance in building n8n workflows

## 📋 Available Tools

### Core Tools (No Configuration Required)
- `tools_documentation` - Get documentation for any MCP tool
- `search_nodes` - Full-text search across 1,650+ n8n nodes
- `get_node` - Get detailed node information and documentation
- `validate_node` - Validate node configurations
- `validate_workflow` - Complete workflow validation
- `search_templates` - Search through 2,352 workflow templates
- `get_template` - Get complete workflow JSON from templates

### n8n Management Tools (Requires API Configuration)
If you have an n8n instance running, you can enable additional tools:
- `n8n_create_workflow` - Create workflows directly in your n8n instance
- `n8n_get_workflow` - Retrieve workflows
- `n8n_update_full_workflow` - Update entire workflows
- `n8n_update_partial_workflow` - Update workflows using diff operations
- `n8n_list_workflows` - List all workflows
- `n8n_test_workflow` - Test workflow execution
- `n8n_executions` - Manage workflow executions
- `n8n_manage_credentials` - Manage credentials
- And more...

## 🔑 Connect to Your n8n Instance (Optional)

To enable n8n management tools, update your MCP configuration to include your n8n API credentials:

```json
{
  "mcpServers": {
    "n8n-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "n8n-mcp@latest"
      ],
      "env": {
        "N8N_API_URL": "https://your-n8n-instance.com",
        "N8N_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Getting Your n8n API Key

1. Log into your n8n instance
2. Go to **Settings** → **API**
3. Click **Create API Key**
4. Copy the generated key
5. Add it to the MCP configuration above

## 🚀 Usage Examples

### Example 1: Search for Nodes
```
"Find all nodes related to Slack integration"
```

### Example 2: Get Node Documentation
```
"Show me documentation for the HTTP Request node"
```

### Example 3: Validate a Workflow
```
"Validate this n8n workflow configuration: [paste workflow JSON]"
```

### Example 4: Search Templates
```
"Find workflow templates for sending Slack notifications"
```

### Example 5: Build a Workflow
```
"Help me build an n8n workflow that:
1. Triggers on a webhook
2. Processes the data
3. Sends a notification to Slack"
```

## 📚 Additional Resources

- **GitHub Repository**: https://github.com/czlonkowski/n8n-mcp
- **Documentation**: Check the README for comprehensive guides
- **Hosted Version**: dashboard.n8n-mcp.com (if you prefer not to self-host)
- **Templates**: 2,352 pre-built workflows available via search

## ⚠️ Important Safety Warning

**NEVER edit production workflows directly with AI!** Always:
- Make a copy of your workflow before using AI tools
- Test in development environment first
- Export backups of important workflows
- Validate changes before deploying to production

## 🔧 Troubleshooting

### MCP Server Not Showing Up
1. Ensure you've restarted Cursor completely
2. Check the MCP panel in Cursor (look for the MCP icon)
3. Verify the configuration in `~/.cursor/mcp.json`

### Connection Issues
- If using API tools, verify your `N8N_API_URL` and `N8N_API_KEY` are correct
- Ensure your n8n instance is accessible from your development machine
- Check firewall and network settings

### Getting Help
- Check the n8n-mcp GitHub issues: https://github.com/czlonkowski/n8n-mcp/issues
- Review the documentation in the repository
- Use the `tools_documentation` tool to get help on specific MCP tools

## 💡 Pro Tips

1. **Start with `tools_documentation()`** - This shows you all available tools and how to use them
2. **Use templates first** - 2,352 pre-built workflows can save you time
3. **Validate early and often** - Use validation tools before deploying
4. **Parallel execution** - The MCP can handle multiple requests simultaneously
5. **Attribution** - Always credit template authors when using their work

---

**Ready to build workflows!** Try asking: "Show me the available n8n-mcp tools" or "Find Slack notification templates"
