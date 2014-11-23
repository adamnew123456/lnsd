-- Wireshark LNS protocol dissector. Released under the GPLv2 to comply with
-- Wireshark's license.
--
-- Adam Marchetti <adamnew123456@gmail.com>
lns_protocol = Proto("lns", "LAN Naming System")

local LNS_ANNOUNCE = 1
local LNS_CONFLICT = 2

function lns_protocol.dissector(buffer, packetinfo, tree)
    packetinfo.cols.protocol = "LNS"

    local subtree = tree:add(lns_protocol, buffer(), "LNS Protocol Data")

    -- Figure out what kind of packet this is
    local packet_type = buffer(0, 1):uint()

    if packet_type == LNS_ANNOUNCE then
        subtree:add(buffer(0, 1), "Announce Message")

        -- Figure out what the actual hostname is, by scanning until we hit a
        -- NUL byte
        local hostname = buffer(1):string():match("[^\0]+")
        subtree:add(buffer(1), "Hostname: " .. hostname)
    elseif packet_type == LNS_CONFLICT then
        subtree:add(buffer(0, 1), "Conflict Message")
    else
        subtree:add(buffer(0, 1), "Invalid Message Type")
    end
end

dis_table = DissectorTable.get("udp.port")
dis_table:add(15051, lns_protocol)
