
# AxonOps Dashboard ansible role

## Configuration

The configuration is quite simple and it only requires a few switches.

### Listen address and port

We recommend you set up a proxy in front of the dashboard such as nginx. In that case you'd want the dashboard listening on localhost (default). A good role you can look at for this is the [geerlingguy one](https://github.com/geerlingguy/ansible-role-nginx)

```yaml
# Override the IP and port that axon-dash should listen on
axon_dash_listen_address: 127.0.0.1
axon_dash_listen_port: 3000
```

### AxonOps server

You will also need to configure the URL of the server. The default configuration assumes both are on the same server.

```yaml
axon_dash_server_endpoint: http://127.0.0.1:8080
```
