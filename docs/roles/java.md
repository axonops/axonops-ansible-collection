# Java Role

## Overview

The `java` role installs Java (JDK or JRE) on target systems. This is a prerequisite for running Apache Cassandra, Elasticsearch, and AxonOps components.

## Requirements

- Ansible 2.9 or higher
- Target system running a supported Linux distribution (RHEL, CentOS, Ubuntu, Debian)
- Internet access or local package repositories

## Role Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `java_use_zulu` | `false` | Use Azul Zulu Java instead of OpenJDK (Debian-based systems only) |
| `java_install_epel` | `false` | Install EPEL repository before installing Java (RHEL-based systems) |
| `java_pkg` | - | Specific Java package to install (defined in playbook) |

## Supported Java Distributions

### OpenJDK (Default)

The role installs OpenJDK by default, which is available on all supported platforms.

### Azul Zulu (Optional)

Azul Zulu OpenJDK builds can be installed on Debian-based systems by setting `java_use_zulu: true`.

## Dependencies

None

## Example Playbooks

### Basic Java 11 Installation

```yaml
- name: Install Java 11
  hosts: cassandra
  become: true
  vars:
    java_pkg: java-11-openjdk-headless

  roles:
    - role: axonops.axonops.java
```

### Java 17 Installation (for Cassandra 5.x)

```yaml
- name: Install Java 17
  hosts: cassandra
  become: true
  vars:
    java_pkg: java-17-openjdk-headless

  roles:
    - role: axonops.axonops.java
```

### Using Azul Zulu Java (Debian/Ubuntu)

```yaml
- name: Install Zulu Java 11
  hosts: cassandra
  become: true
  vars:
    java_use_zulu: true
    java_pkg: zulu-11

  roles:
    - role: axonops.axonops.java
```

### With EPEL Repository (RHEL/CentOS)

```yaml
- name: Install Java with EPEL
  hosts: cassandra
  become: true
  vars:
    java_install_epel: true
    java_pkg: java-11-openjdk-headless

  roles:
    - role: axonops.axonops.java
```

### Complete Stack with Java

```yaml
- name: Deploy Cassandra Stack with Java
  hosts: cassandra
  become: true
  vars:
    java_pkg: java-11-openjdk-headless
    axon_java_agent: "axon-cassandra4.1-agent"
    cassandra_version: 4.1.3

  roles:
    - role: axonops.axonops.java
      tags: java

    - role: axonops.axonops.agent
      tags: agent

    - role: axonops.axonops.cassandra
      tags: cassandra
```

## Java Version Selection Guide

### For Cassandra

| Cassandra Version | Recommended Java Version | Package Name (RHEL/CentOS) | Package Name (Debian/Ubuntu) |
|-------------------|-------------------------|----------------------------|------------------------------|
| 3.11.x | Java 8 | java-1.8.0-openjdk-headless | openjdk-8-jre-headless |
| 4.0.x - 4.1.x | Java 11 | java-11-openjdk-headless | openjdk-11-jre-headless |
| 5.0.x+ | Java 17 | java-17-openjdk-headless | openjdk-17-jre-headless |

### For Elasticsearch

| Elasticsearch Version | Recommended Java Version |
|----------------------|-------------------------|
| 6.x | Java 11 |
| 7.x | Java 11 or 17 |
| 8.x | Java 17 |

### For AxonOps Server

| Component | Recommended Java Version |
|-----------|-------------------------|
| AxonOps Server | Java 17 |
| AxonOps Dashboard | Not required (Node.js application) |

## Platform-Specific Examples

### RHEL/CentOS/Rocky Linux

```yaml
- name: Install Java on RHEL
  hosts: rhel_servers
  become: true
  vars:
    java_pkg: java-11-openjdk-headless

  roles:
    - role: axonops.axonops.java
```

### Ubuntu/Debian

```yaml
- name: Install Java on Ubuntu
  hosts: ubuntu_servers
  become: true
  vars:
    java_pkg: openjdk-11-jre-headless

  roles:
    - role: axonops.axonops.java
```

### Amazon Linux 2

```yaml
- name: Install Java on Amazon Linux 2
  hosts: amazon_linux
  become: true
  vars:
    java_pkg: java-11-amazon-corretto-headless

  roles:
    - role: axonops.axonops.java
```

## Advanced Configuration

### Multiple Java Versions

If you need multiple Java versions, you can use alternatives:

```yaml
- name: Install and Configure Java Alternatives
  hosts: servers
  become: true
  vars:
    java_pkg: java-17-openjdk-headless

  roles:
    - role: axonops.axonops.java

  post_tasks:
    - name: Set Java 17 as default
      community.general.alternatives:
        name: java
        path: /usr/lib/jvm/java-17-openjdk-amd64/bin/java
```

### Custom JAVA_HOME

```yaml
- name: Install Java and Set JAVA_HOME
  hosts: servers
  become: true
  vars:
    java_pkg: java-11-openjdk-headless

  roles:
    - role: axonops.axonops.java

  post_tasks:
    - name: Set JAVA_HOME in environment
      ansible.builtin.lineinfile:
        path: /etc/environment
        regexp: '^JAVA_HOME='
        line: 'JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64'
```

## Tags

- `java`: Apply all Java installation tasks

## Notes

- **Headless Packages**: Use `-headless` packages (e.g., `java-11-openjdk-headless`) for server installations to avoid installing unnecessary GUI components
- **Package Names**: Package names vary between distributions. Check your distribution's package repository for exact names
- **Cross-Platform Support**: The role uses the generic `package` module for improved compatibility across different Linux distributions (RHEL, Debian, Ubuntu, etc.)
- **JAVA_HOME**: Most modern installations automatically set JAVA_HOME, but verify if your application requires it
- **Updates**: The role installs the latest available version of the specified Java package. Use package pinning if you need a specific minor version
- **Zulu Java**: Only available on Debian-based systems through this role

## Verification

After installation, verify Java is installed correctly:

```bash
java -version
```

Expected output (for Java 11):
```
openjdk version "11.0.x" 2023-xx-xx
OpenJDK Runtime Environment (build 11.0.x+x)
OpenJDK 64-Bit Server VM (build 11.0.x+x, mixed mode, sharing)
```

## Troubleshooting

### Issue: Package not found

**Solution**: Ensure the package name is correct for your distribution. Use the platform's package manager to search:

```bash
# RHEL/CentOS
yum search openjdk

# Ubuntu/Debian
apt-cache search openjdk
```

### Issue: Multiple Java versions conflict

**Solution**: Use the `alternatives` command to manage multiple Java installations:

```bash
# RHEL/CentOS
alternatives --config java

# Ubuntu/Debian
update-alternatives --config java
```

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
