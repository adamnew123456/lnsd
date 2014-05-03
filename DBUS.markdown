# DBus

This implementation, `lnsd`, uses DBus to communicate with user programs. The DBus
interface is simple, but documented here if you're curious. Normally, you'll want
to use the `lns-query` program to interact with `lnsd`.

# Interface

The DBus interface is provided via the path "/org/adamnew123456/lnsd" and the
name is "org.adamnew123456.lnsd".

## QueryName(name) -> ip

This gets the IP address associated with a certain hostname. If there is no
associated hostname, this returns an empty string.

## QueryHost(ip) -> name

This gets the hostname associated with a certain IP address. If there is no
associated hostname, this returns the empty string.

## QueryAll() -> {name: ip}

This gets a copy of the entire mapping between hostnames and IP addresses.
