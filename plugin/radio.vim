" :Radio          toggle the radio UI      :Radio play groove / local bandung / tag jazz / search bbc
if exists('g:loaded_radio') | finish | endif
let g:loaded_radio = 1
if has('nvim')
  command! -nargs=* Radio lua require("radio").toggle(<q-args>)
else
  let s:py = expand('<sfile>:p:h:h') . '/radio.py'
  command! -nargs=* Radio execute 'terminal ++close python3' shellescape(s:py) <q-args>
endif
