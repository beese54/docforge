--[[ docforge pandoc filter.

1. Mermaid code blocks become numbered figures (rendered to PDF by mermaid-cli).
   Caption: a `%% caption: ...` line in the diagram, else "Diagram".
   A render failure keeps the code block and prints DOCFORGE-MERMAID-FAILED to stderr.
2. With --file-scope every input file becomes a top-level Div. Pandoc only rewrites links whose path matches
   an input argument literally, so a link like ../README.md#x inside docs/ would break. This filter resolves
   each link and image relative to its own file:
     - link to a file in the manual  -> internal link to that file's section/anchor
     - link to any other repo file    -> plain text (a relative repo path means nothing on paper)
     - relative image                 -> path relative to the repository root
Metadata in: docforge-files (input paths, in order), docforge-tmp (scratch dir for diagrams).
]]

local files, tmpdir = {}, "."

local function normalize(path)
  local out = {}
  for part in path:gmatch("[^/]+") do
    if part == ".." then
      if #out == 0 or out[#out] == ".." then table.insert(out, "..") else table.remove(out) end
    elseif part ~= "." then
      table.insert(out, part)
    end
  end
  return table.concat(out, "/")
end

local function dirname(path)
  return path:match("^(.*)/[^/]*$") or ""
end

local function is_external(target)
  return target:match("^[%a][%w+.-]*:") ~= nil or target:sub(1, 2) == "//"
end

local function url_decode(s)
  return (s:gsub("%%(%x%x)", function(h) return string.char(tonumber(h, 16)) end))
end

local function mermaid_figure(block)
  local code = block.text
  local caption = code:match("%%%%%s*caption:%s*([^\n]+)") or "Diagram"
  local name = pandoc.sha1(code)
  local src = tmpdir .. "/" .. name .. ".mmd"
  local out = tmpdir .. "/" .. name .. ".pdf"
  local fh = io.open(src, "w")
  fh:write(code)
  fh:close()
  local args = { "-i", src, "-o", out, "--pdfFit", "-q" }
  -- Containers usually cannot give Chromium its own sandbox; the image points this at a puppeteer config.
  local puppeteer = os.getenv("DOCFORGE_PUPPETEER_CONFIG")
  if puppeteer and puppeteer ~= "" then
    table.insert(args, "-p")
    table.insert(args, puppeteer)
  end
  local ok, err = pcall(pandoc.pipe, "mmdc", args, "")
  if not ok then
    io.stderr:write("DOCFORGE-MERMAID-FAILED: " .. caption .. ": " .. tostring(err) .. "\n")
    return nil
  end
  return pandoc.Figure(pandoc.Plain({ pandoc.Image({}, out) }), { pandoc.Plain(pandoc.Inlines(caption)) })
end

local function resolver(file, ids)
  local base = dirname(file)
  return {
    Link = function(link)
      local target = link.target
      if target == "" or target:sub(1, 1) == "#" or is_external(target) then return nil end
      local path, anchor = target:match("^([^#]*)#?(.*)$")
      path = url_decode(path:gsub("%?.*$", ""))
      local rel = normalize(path:sub(1, 1) == "/" and path:sub(2) or (base == "" and path or base .. "/" .. path))
      local id = ids[rel]
      if id == nil then return pandoc.Span(link.content) end
      link.target = "#" .. id .. (anchor ~= "" and ("__" .. anchor) or "")
      return link
    end,
    Image = function(img)
      if is_external(img.src) or img.src:sub(1, 1) == "/" then return nil end  -- includes rendered diagrams
      img.src = normalize(base == "" and img.src or base .. "/" .. img.src)
      return img
    end,
  }
end

function Pandoc(doc)
  local meta_files = doc.meta["docforge-files"]
  if meta_files then
    for _, f in ipairs(meta_files) do table.insert(files, pandoc.utils.stringify(f)) end
  end
  if doc.meta["docforge-tmp"] then tmpdir = pandoc.utils.stringify(doc.meta["docforge-tmp"]) end

  doc = doc:walk({ CodeBlock = function(b) if b.classes:includes("mermaid") then return mermaid_figure(b) end end })

  -- Top-level Divs map 1:1 onto input files, in order (that is how --file-scope combines them).
  local ids, owner, n = {}, {}, 0
  for k, block in ipairs(doc.blocks) do
    if block.t == "Div" and block.identifier ~= "" then
      n = n + 1
      if files[n] then
        ids[normalize(files[n])] = block.identifier
        owner[k] = files[n]
      end
    end
  end
  for k, file in pairs(owner) do
    doc.blocks[k] = doc.blocks[k]:walk(resolver(file, ids))
  end
  return doc
end
