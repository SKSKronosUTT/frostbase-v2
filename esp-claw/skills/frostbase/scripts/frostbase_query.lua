-- Consulta de solo lectura a FrostBase usando cap_http_request.
-- El token y la URL se leen de private/config.txt; nunca se imprimen.

local capability = require("capability")
local storage = require("storage")

local function fail(message)
    error("[frostbase] " .. message)
end

local function read_config()
    local root = storage.get_root_dir()
    local path = storage.join_path(root, "skills/frostbase/private/config.txt")
    local ok, data = pcall(storage.read_file, path)
    if not ok or type(data) ~= "string" or data == "" then
        fail("falta skills/frostbase/private/config.txt")
    end

    local config = {}
    for line in data:gmatch("[^\r\n]+") do
        local key, value = line:match("^%s*([%w_]+)%s*=%s*(.-)%s*$")
        if key and value ~= "" then
            config[key] = value
        end
    end
    if not config.base then
        fail("config.txt no define base")
    end
    if not config.token then
        fail("config.txt no define token")
    end
    return config
end

local function clamp(value, minimum, maximum, default)
    local number = tonumber(value)
    if not number then
        number = default
    end
    number = math.floor(number)
    if number < minimum then
        return minimum
    end
    if number > maximum then
        return maximum
    end
    return number
end

local function endpoint_path(name, args)
    local values = type(args) == "table" and args or {}
    if name == "fleet-summary" then
        return "/api/v1/agent-read/fleet-summary"
    elseif name == "alerts" then
        return "/api/v1/agent-read/alerts?limit="
            .. tostring(clamp(values.limit, 1, 20, 10))
    elseif name == "alerts-today" then
        return "/api/v1/agent-read/alerts/today?limit="
            .. tostring(clamp(values.limit, 1, 20, 10))
    elseif name == "truck-status" then
        local truck_id = tonumber(values.truck_id)
        if not truck_id or truck_id < 1 or truck_id % 1 ~= 0 then
            fail("truck_id debe ser un entero positivo")
        end
        return "/api/v1/agent-read/trucks/"
            .. string.format("%d", truck_id)
            .. "/status"
    elseif name == "trips-active" then
        return "/api/v1/agent-read/trips/active?limit="
            .. tostring(clamp(values.limit, 1, 10, 5))
    elseif name == "routes-today" then
        return "/api/v1/agent-read/routes/today?limit="
            .. tostring(clamp(values.limit, 1, 10, 6))
    elseif name == "thresholds" then
        return "/api/v1/agent-read/thresholds"
    end
    fail("endpoint no permitido: " .. tostring(name))
end

local function run()
    local input = type(args) == "table" and args or {}
    local config = read_config()
    local base = config.base:gsub("/+$", "")
    local endpoint = input.endpoint
    if type(endpoint) ~= "string" or endpoint == "" then
        fail("args.endpoint es obligatorio")
    end

    local payload = {
        url = base .. endpoint_path(endpoint, input),
        method = "GET",
        headers = {
            Authorization = "Bearer " .. config.token,
            Accept = "application/json",
        },
        timeout_ms = 15000,
        max_body_bytes = 16384,
    }

    local ok, output, err = capability.call("http_request", payload, {
        source_cap = "frostbase",
    })
    if not ok then
        fail("http_request falló: " .. tostring(err or output))
    end
    print(output)
end

local ok, err = xpcall(run, debug.traceback)
if not ok then
    error(err)
end
