# LAN Name Service

The LAN Name Service is designed to be a simple peer-to-peer host naming
system which works via a LAN. LNS is meant to be an alternative to populating 
`/etc/hosts` and configuring a static IP address.

The protocol is designed to be as minimal as possible, for a couple reasons:

 - To be as easy as possible to implement.
 - To avoid having any inconsistency issues. By having as few elements in the
   protocol as possible, the information which is transferred between hosts is
   minimal. This prevents ordering dependencies from developing, and thus avoiding
   ordering bugs.

# Protocol

- `ANNOUNCE <broadcast> $name`
  Inform all alive hosts that this node is alive and bound to the given name.
  This should be sent at even intervals, starting when the host joins the 
  network.

# Packet Contents

## Contents of LNS ANNOUNCE

      1    <var>    <var>
    +---+--------+---------+
    | 1 |  Name  | Packing |
    +---+--------+---------+

 - "Name" is the name that this host wants to associate with.
 - "Packing" is a series of NUL bytes, used to make sure the data size is 512.

Note that the "Name" field cannot contain characters below 33 (ASCII '!') or
above 126 (ASCII '~'). This is to ensure that all characters are printable.
