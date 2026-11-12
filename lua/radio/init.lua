-- radio.nvim: floating terminal around radio.py. :Radio toggles the UI (music keeps playing while hidden),
-- :Radio <args> runs a one-off command (play groove, local bandung, ...). require("radio").now() -> statusline text.
local M = {}
local root = vim.fn.fnamemodify(debug.getinfo(1, "S").source:sub(2), ":h:h:h")
local NOW = vim.fn.expand("~/.cache/radio/now")
local buf, win

M.opts = { width = 0.8, height = 0.8, border = "rounded", python = "python3" }

function M.setup(opts)
  M.opts = vim.tbl_extend("force", M.opts, opts or {})
end

-- ponytail: reads the file on every statusline redraw; cache by mtime if it ever shows up in a profile
function M.now()
  local f = io.open(NOW)
  if not f then return "" end
  local s = f:read("*a"); f:close()
  return (s:gsub("%s+$", ""))
end

local function float(b)
  local W, H = vim.o.columns, vim.o.lines - vim.o.cmdheight - 1
  local w, h = math.floor(W * M.opts.width), math.floor(H * M.opts.height)
  local w_id = vim.api.nvim_open_win(b, true, {
    relative = "editor", width = w, height = h, col = math.floor((W - w) / 2), row = math.floor((H - h) / 2),
    style = "minimal", border = M.opts.border,
  })
  vim.cmd.startinsert()
  return w_id
end

local function term(cmd, on_exit)
  local b = vim.api.nvim_create_buf(false, true)
  local w_id = float(b)
  local o = { on_exit = on_exit }
  if vim.fn.has("nvim-0.11") == 1 then o.term = true; vim.fn.jobstart(cmd, o) else vim.fn.termopen(cmd, o) end
  return b, w_id
end

function M.toggle(args)
  if vim.fn.executable("mpv") == 0 and vim.fn.executable("ffplay") == 0 then
    return vim.notify("radio: install mpv first (brew install mpv / apt install mpv)", vim.log.levels.ERROR)
  end
  local cmd = { M.opts.python, root .. "/radio.py" }
  if args and args ~= "" then -- one-off command in its own window, closes when done
    vim.list_extend(cmd, vim.split(args, "%s+", { trimempty = true }))
    local b
    b = term(cmd, function() vim.schedule(function() pcall(vim.api.nvim_buf_delete, b, { force = true }) end) end)
    return
  end
  if win and vim.api.nvim_win_is_valid(win) then -- hide: process (and music) keeps running
    vim.api.nvim_win_hide(win); win = nil
    return
  end
  if buf and vim.api.nvim_buf_is_valid(buf) then
    win = float(buf)
    return
  end
  buf, win = term(cmd, function()
    vim.schedule(function() pcall(vim.api.nvim_buf_delete, buf, { force = true }) end)
    buf, win = nil, nil
  end)
end

return M
