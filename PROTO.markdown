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
  
  Upon receiving an ANNOUNCE, a node should first ensure that another host isn't
  already bound to $name - if it is, then send a CONFLICT message to the
  host making the ANNOUNCE. If the name is free, then remove any previous names
  given by the current host, and insert the $name-host pair into the mapping.

- `CONFLICT <unicast>`
  Inform a host that it is using a name which is already bound on the sender by
  a different host.
  
  Upon receiving a CONFLICT, a node should immediately stop issuing periodic
  ANNOUNCE requests until another name can be selected. This may mean either:
  
  - Falling-back onto some other names given to the node.
  - Terminating and letting the user restart with a new node name.

# Packet Contents

## Contents of LNS ANNOUNCE

       <var>   1    <var>    <var>
    +------------+--------+---------+
    | Header | 1 |  Name  | Packing |
    +------------+--------+---------+

 - "Header" is a standard UDP header.
 - "Name" is the name that this host wants to associate with.
 - "Packing" is a series of NUL bytes, used to make sure the data size is 512.

Note that the "Name" field cannot contain characters below 33 (ASCII '!') or
above 126 (ASCII '~'). This is to ensure that all characters are printable.

## Contents of LNS CONFLICT

      <var>    1     511
    +------------+---------+
    | Header | 2 | Packing |
    +------------+---------+

 - "Header" is a standard UDP header.
 - "Packing" is a series of NUL bytes.
