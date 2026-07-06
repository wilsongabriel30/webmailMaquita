

-- ===== Anti-spoofing de dominio propio (Maquita) =====
local maq_local_domains = rspamd_config:add_map({
  url = '/etc/rspamd/local.d/maps/local_domains.map',
  description = 'Dominios propios hospedados',
  type = 'set',
})

local function maq_check_own_spoof(task)
  if task:get_user() then return false end
  local ip = task:get_from_ip()
  if ip and ip:is_valid() and ip:is_local() then return false end
  local from = task:get_from('smtp')
  if not (from and from[1] and from[1].domain) then from = task:get_from('mime') end
  if not (from and from[1] and from[1].domain) then return false end
  local fdom = tostring(from[1].domain):lower()
  local function maq_is_ours(d)
    while d and d ~= '' do
      if maq_local_domains:get_key(d) then return true end
      local nd = d:gsub('^[^.]+%.', '', 1)
      if nd == d then break end
      d = nd
    end
    return false
  end
  if not (maq_local_domains and maq_is_ours(fdom)) then return false end
  if task:has_symbol('R_DKIM_ALLOW') or task:has_symbol('R_SPF_ALLOW')
     or task:has_symbol('DMARC_POLICY_ALLOW') then return false end
  return true, 1.0, fdom
end

local maq_id = rspamd_config:register_symbol({
  name = 'MAQ_OWN_DOMAIN_SPOOF',
  callback = maq_check_own_spoof,
  score = 12.0,
  description = 'Suplantacion de un dominio propio desde el exterior (spoofing)',
  group = 'spoofing',
})
rspamd_config:register_dependency('MAQ_OWN_DOMAIN_SPOOF', 'DKIM_CHECK')
rspamd_config:register_dependency('MAQ_OWN_DOMAIN_SPOOF', 'SPF_CHECK')
rspamd_config:register_dependency('MAQ_OWN_DOMAIN_SPOOF', 'DMARC_CALLBACK')

-- ===== Sextorsion con billetera bitcoin (defensa en profundidad) =====
rspamd_config:register_symbol({
  name = 'MAQ_SEXTORTION_BTC',
  callback = function(task)
    local tp = task:get_text_parts()
    if not tp then return false end
    for _,p in ipairs(tp) do
      local c = p:get_content()
      if c then
        local txt = tostring(c):lower()
        if (txt:find('bitcoin') or txt:find('bc1') or txt:find('btc wallet'))
           and (txt:find('hackead') or txt:find('masturb') or txt:find('pornograf')
                or txt:find('reputacion') or txt:find('camara')) then
          return true, 1.0
        end
      end
    end
    return false
  end,
  score = 7.0,
  description = 'Patron de sextorsion con billetera bitcoin',
  group = 'spam',
})

-- ===== Suplantacion del nombre visible (RRHH falso 2026-07-06) =====
-- Display name menciona la marca (maquita/mcch) pero el remitente es externo
-- y no es un dominio propio. Score 6 = va a Junk directo.
rspamd_config:register_symbol({
  name = "MAQ_DISPNAME_SPOOF",
  callback = function(task)
    if task:get_user() then return false end
    local ip = task:get_from_ip()
    if ip and ip:is_valid() and ip:is_local() then return false end
    local from = task:get_from("mime")
    if not (from and from[1]) then return false end
    local name = (from[1].name or ""):lower()
    if not (name:find("maquita") or name:find("mcch")) then return false end
    local dom = tostring(from[1].domain or ""):lower()
    local function is_ours(d)
      while d and d ~= "" do
        if maq_local_domains:get_key(d) then return true end
        local nd = d:gsub("^[^.]+%.", "", 1)
        if nd == d then break end
        d = nd
      end
      return false
    end
    if dom ~= "" and is_ours(dom) then return false end
    -- dominios propios del Zimbra tambien son legitimos
    local zimbra = { ["maquita.com.ec"]=true, ["mcch.com.ec"]=true, ["fundmcch.com.ec"]=true }
    if zimbra[dom] or dom:match("%.maquita%.com%.ec$") or dom:match("%.mcch%.com%.ec$") then return false end
    return true, 1.0, name
  end,
  score = 6.0,
  description = "Nombre visible dice Maquita/MCCH pero remitente externo",
  group = "spoofing",
})
