-- Build a mono REAPER project from the supplied De-Feedback track state.
local r = reaper
local title = "De-Feedback template"
local automatic = os.getenv("DEFEEDBACK_TEMPLATE_PROFILE") == "automatic"
local function report(message)
    if automatic then
        local path = os.getenv("DEFEEDBACK_TEMPLATE_OUTPUT")
        local log = path and io.open(path .. ".log", "a")
        if log then
            log:write(os.date("%Y-%m-%d %H:%M:%S "), message, "\n")
            log:close()
        end
        r.ShowConsoleMsg(message .. "\n")
    else
        r.ShowMessageBox(message, title, 0)
    end
end
local major, minor = r.GetAppVersion():match("^(%d+)%.(%d+)")
if not major or tonumber(major) < 7 or (tonumber(major) == 7 and tonumber(minor) < 43) then
    report("REAPER 7.43 or newer is required for automatic mono bus configuration.")
    return
end
local profiles = {
    ["1ch"] = { count = 1, first_input = 1 },
    ["2ch"] = { count = 2, first_input = 1 },
    ["4ch"] = { count = 4, first_input = 1 },
    ["8ch"] = { count = 8, first_input = 1 },
    ["cq12t-5ch"] = { count = 5, first_input = 6 },
    ["cq18t-8ch"] = { count = 8, first_input = 9 },
    ["cq20b-8ch"] = { count = 8, first_input = 9 },
}

local function fail(message)
    error(message, 0)
end

local _, script_path = r.get_action_context()
local directory = script_path:match("^(.*[/\\])")
local source_path = directory .. "plugin-state.RPP"
local source = io.open(source_path, "r")
if not source then
    report("Missing source project: " .. source_path)
    return
end
local contents = source:read("*a"):gsub("\r\n", "\n")
source:close()
-- Tracks are top-level project chunks; retain the first complete track.
local track_chunk = contents:match("\n  (<TRACK .-\n  >)")
if not track_chunk then
    report("The source project has no readable track.")
    return
end

if r.CountTracks(0) ~= 0 or r.TrackFX_GetCount(r.GetMasterTrack(0)) ~= 0 then
    report("Open a new empty project tab before running this action.")
    return
end
local accepted, choice = true, "automatic"
if automatic then
    local count = tonumber(os.getenv("DEFEEDBACK_TEMPLATE_CHANNELS"))
    local first_input = tonumber(os.getenv("DEFEEDBACK_TEMPLATE_FIRST_INPUT"))
    if not count or count % 1 ~= 0 or count < 1 or count > 8
        or not first_input or first_input % 1 ~= 0 or first_input < 1 then
        report("Invalid automatic template routing.")
        return
    end
    profiles.automatic = { count = count, first_input = first_input }
else
    accepted, choice = r.GetUserInputs(title, 1,
        "Profile (1ch/2ch/4ch/8ch/cq12t-5ch/cq18t-8ch/cq20b-8ch),extrawidth=180", "8ch")
end
if not accepted then return end
choice = choice:match("^%s*(.-)%s*$"):lower()
local profile = profiles[choice]
if not profile then
    report("Unknown template profile.")
    return
end
local output_directory = directory .. "templates"
local output_path = output_directory .. "/defeedback-" .. choice .. ".RPP"
if automatic then output_path = os.getenv("DEFEEDBACK_TEMPLATE_OUTPUT") end
if r.file_exists(output_path) and automatic then
    r.Main_openProject(output_path)
    local valid = r.CountTracks(0) == profile.count
    for index = 0, r.CountTracks(0) - 1 do
        local track = r.GetTrack(0, index)
        local _, inputs, outputs = r.TrackFX_GetIOSize(track, 0)
        valid = valid and r.TrackFX_GetCount(track) == 1 and inputs == 1 and outputs == 1
    end
    if not valid then
        for index = 0, r.CountTracks(0) - 1 do
            r.SetMediaTrackInfo_Value(r.GetTrack(0, index), "B_MUTE", 1)
        end
        report("ERROR: Saved project failed mono validation; tracks muted. Move the saved project to regenerate it.")
    else
        report("Opened saved mono project: " .. output_path)
    end
    return
end
if r.file_exists(output_path) then
    report("Template already exists. Move or rename it before regenerating:\n" .. output_path)
    return
end

local created = {}
r.Undo_BeginBlock()
r.PreventUIRefresh(1)
local success, failure = pcall(function()
    for channel = 1, profile.count do
        local input = profile.first_input + channel - 1
        r.InsertTrackAtIndex(channel - 1, false)
        local track = r.GetTrack(0, channel - 1)
        created[#created + 1] = track
        -- Assign fresh identifiers while preserving plugin parameter state.
        local identifiers = {}
        local chunk = track_chunk:gsub("{%x+%-%x+%-%x+%-%x+%-%x+}", function(identifier)
            identifiers[identifier] = identifiers[identifier] or r.genGuid()
            return identifiers[identifier]
        end)
        -- Load bypassed, configure mono, then activate before adding another FX.
        chunk = chunk:gsub("BYPASS %d+ %d+ %d+", "BYPASS 1 0 0")
        if not r.SetTrackStateChunk(track, chunk, false) then
            fail("Could not load the source track.")
        end
        if r.TrackFX_GetCount(track) ~= 1 then
            fail("The source must contain exactly one De-Feedback effect per track.")
        end
        local _, name = r.TrackFX_GetFXName(track, 0)
        if not name:find("De%-Feedback") then fail("De-Feedback did not load.") end
        if not r.TrackFX_SetNamedConfigParm(track, 0, "channel_config", "1") then
            fail("REAPER could not request a mono plugin bus. Update REAPER or configure the bus manually.")
        end
        local _, inputs, outputs = r.TrackFX_GetIOSize(track, 0)
        if inputs ~= 1 or outputs ~= 1 then
            fail("De-Feedback did not expose one input and one output. Template creation stopped.")
        end
        r.TrackFX_SetPinMappings(track, 0, 0, 0, 1, 0)
        r.TrackFX_SetPinMappings(track, 0, 1, 0, 1, 0)
        r.GetSetMediaTrackInfo_String(track, "P_NAME",
            ("De-Feedback %d (in %d > out %d)"):format(channel, input, channel), true)
        r.SetMediaTrackInfo_Value(track, "I_RECINPUT", input - 1)
        r.SetMediaTrackInfo_Value(track, "I_RECMODE", 2) -- Monitor without recording.
        r.SetMediaTrackInfo_Value(track, "I_RECARM", 1)
        r.SetMediaTrackInfo_Value(track, "I_RECMON", 1)
        r.SetMediaTrackInfo_Value(track, "B_MUTE", 0)
        r.SetMediaTrackInfo_Value(track, "B_MAINSEND", 0)
        while r.GetTrackNumSends(track, 1) > 0 do
            r.RemoveTrackSend(track, 1, 0)
        end
        local send = r.CreateTrackSend(track, nil)
        if send < 0
            or not r.SetTrackSendInfo_Value(track, 1, send, "I_SRCCHAN", 1024)
            or not r.SetTrackSendInfo_Value(track, 1, send, "I_DSTCHAN", 1024 + channel - 1)
            or not r.SetTrackSendInfo_Value(track, 1, send, "I_SENDMODE", 0) then
            fail("Could not create the mono hardware send.")
        end
        r.TrackFX_SetEnabled(track, 0, true)
    end
end)
if not success then
    for i = #created, 1, -1 do r.DeleteTrack(created[i]) end
end
r.PreventUIRefresh(-1)
r.TrackList_AdjustWindows(false)
r.UpdateArrange()
r.Undo_EndBlock("Create De-Feedback mono template", -1)
if not success then
    report(failure)
    return
end

r.GetSetProjectInfo(0, "PROJECT_SRATE", 48000, true)
r.GetSetProjectInfo(0, "PROJECT_SRATE_USE", 1, true)
-- Block size, bit depth, and periods belong to the device INI profile.
r.RecursiveCreateDirectory(output_path:match("^(.*)[/\\]"), 0)
r.Main_SaveProjectEx(0, output_path, 8)
if not r.file_exists(output_path) then
    report("Could not save the template. Save the open project manually.")
    return
end
report("Saved " .. output_path .. "\nMono plugin buses and routing were checked. " ..
    "Verify 48 kHz, 24-bit, 64 samples, and 3 periods in the ALSA device settings. " ..
    "Eight-mono performance still requires a hardware test.")
