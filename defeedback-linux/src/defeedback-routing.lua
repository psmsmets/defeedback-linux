-- Create independent mono inserts for the active REAPER audio device.
local r = reaper
local title = "De-Feedback routing"

local function message(text)
    r.ShowMessageBox(text, title, 0)
end

if r.CountTracks(0) ~= 0 or r.TrackFX_GetCount(r.GetMasterTrack(0)) ~= 0 then
    message("Open a new empty project tab before creating a De-Feedback profile.")
    return
end

local inputs = r.GetNumAudioInputs()
local outputs = r.GetNumAudioOutputs()
if math.min(inputs, outputs) < 1 then
    message("Select a device with capture and playback channels in Preferences > Audio > Device.")
    return
end

local profiles = { solo = 1, duo = 2, quad = 4 }
local ok, response = r.GetUserInputs(
    title, 3, "Profile (auto/solo/duo/quad),First input (1-based),First output (1-based),extrawidth=90",
    "auto,1,1")
if not ok then return end
local profile, first_input, first_output = response:match("^%s*(%a+)%s*,%s*(%d+)%s*,%s*(%d+)%s*$")
if not profile then
    message("Enter auto, solo, duo, or quad and two positive channel numbers.")
    return
end
profile = profile:lower()
first_input, first_output = tonumber(first_input), tonumber(first_output)
-- Auto uses the channels available from the selected starting sockets.
local available = math.min(inputs - first_input + 1, outputs - first_output + 1)
local automatic = available >= 4 and 4 or available >= 2 and 2 or 1
local count = profile == "auto" and automatic or profiles[profile]
if not count or first_input < 1 or first_output < 1 or count > available then
    message(("The profile or channel range is invalid. REAPER sees %d inputs and %d outputs."):format(inputs, outputs))
    return
end

local fx_name
local index = 0
while true do
    local found, name = r.EnumInstalledFX(index)
    if not found then break end
    local effect = name:lower():match("^vst3:%s*([^%(]+)")
    if effect and effect:gsub("[%s%-]", "") == "defeedback" then
        fx_name = name
        break
    end
    index = index + 1
end
if not fx_name then
    message("De-Feedback VST3 is missing. Scan ~/.vst3 in Preferences > Plug-ins > VST and retry.")
    return
end

r.Undo_BeginBlock()
r.PreventUIRefresh(1)
local created = {}
local failure
for channel = 0, count - 1 do
    local input, output = first_input + channel, first_output + channel
    r.InsertTrackAtIndex(channel, false)
    local track = r.GetTrack(0, channel)
    created[#created + 1] = track
    r.GetSetMediaTrackInfo_String(track, "P_NAME", ("De-Feedback %d (in %d > out %d)"):format(channel + 1, input, output), true)
    r.SetMediaTrackInfo_Value(track, "B_MUTE", 1)
    r.SetMediaTrackInfo_Value(track, "B_MAINSEND", 0)
    r.SetMediaTrackInfo_Value(track, "I_RECINPUT", input - 1)
    r.SetMediaTrackInfo_Value(track, "I_RECMODE", 2) -- Monitoring only.
    r.SetMediaTrackInfo_Value(track, "I_RECMON", 1)
    r.SetMediaTrackInfo_Value(track, "I_RECARM", 1)
    local send = r.CreateTrackSend(track, nil) -- Send directly to a hardware output.
    local fx = r.TrackFX_AddByName(track, fx_name, false, -1)
    if send < 0 or fx < 0
        or not r.SetTrackSendInfo_Value(track, 1, send, "I_SRCCHAN", 1024)
        or not r.SetTrackSendInfo_Value(track, 1, send, "I_DSTCHAN", 1024 + output - 1) then
        failure = "Could not create the hardware send or load De-Feedback. Check the device and VST3 scan."
        break
    end
    r.TrackFX_SetEnabled(track, fx, false)
end
if failure then
    for i = #created, 1, -1 do r.DeleteTrack(created[i]) end
end
r.PreventUIRefresh(-1)
r.TrackList_AdjustWindows(false)
r.UpdateArrange()
r.Undo_EndBlock("Create De-Feedback routing", -1)

if failure then
    message(failure)
else
    message(("Created %d mono path(s). Tracks are muted and FX are bypassed. Verify the console patch, then unmute one path at a time and enable its FX."):format(count))
end
