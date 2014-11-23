# JSON

This implementation, `lnsd`, uses a small JSON protocol to communicate between
the network service and other parts of the system. You can use it as well, if
you would like to query the information kept by `lnsd`.

## Port Number

This protocol works over TCP, port 10771. This port is exposed only to localhost,
so no external applications can access information gathered by `lnsd` from outside
the host `lnsd` is running on.

## Protocol

The following types of interactions are possible between the application and `lnsd`:


- Application: HOST[hostname]
- `lnsd`: IP[ip or `null`]

- Application: IP[ip]
- `lnsd`: HOST[hostname or `null`]

- Application: GET-ALL[]
- `lnsd`: NAME-IP-MAPPING[...]

- Application: QUIT[]
- `lnsd` (terminates, makes no response)

## Length Headers

Since `lnsd` uses TCP sockets for sending commands, it also packs a pair of
length bytes into the beginning of its messages.

This pair of length bytes indicate the length (in bytes) of the JSON message
sent immediately after it. It is interpreted as *an unsigned short* with 
*host endianness*.

## JSON Structures

### HOST

A *HOST* structure indicates a hostname, which looks like the following:

    {
        'type': 'name',
        'hostname': 'a hostname'
    }

Note that, when `lnsd` response with a *HOST* message, the *hostname* field may
be `null`. However, the application *cannot* send a *HOST* message with a `null`
*hostname* field.

### IP

An *IP* structure indicates an IPv4 IP address, which looks like the following:

    {
        'type': 'ip',
        'ip': '1.2.3.4'
    }

Note that, when `lnsd` response with a *IP* message, the *ip* field may
be `null`. However, the application *cannot* send a *IP* message with a `null`
*ip* field.

### GET-ALL

A *GET-ALL* structure is a request to retrieve a complete list of hostnames and
IP addresses. It looks like the following:

    {
        'type': 'get-all'
    }

### NAME-IP-MAPPING

A *NAME-IP-MAPPING* structure contains all of the hostnames and their associated
IP addresses. It looks like the following:'

    {
        'type': 'nameipmapping',
        'name_ips': {
            'host_1': 'ip1',
            'host_2': 'ip2',
            ...
        }
    }

### QUIT

A *QUIT* structure tells `lnsd` to terminate. It looks like the following:

    {
        'type': 'quit'
    }
