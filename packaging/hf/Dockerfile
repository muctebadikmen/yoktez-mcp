# Hugging Face Spaces — YÖKTEZ MCP (remote HTTP sunucu)
# Bu dosya HF Space reposunun KÖKÜNDE "Dockerfile" olarak bulunur.
# Kaynak kodu public GitHub reposundan kurar → her rebuild en güncel master'ı alır.
FROM python:3.11-slim

# Tek bağımlılık: paketin kendisi (fastmcp, httpx, bs4, lxml, pypdf, platformdirs onunla gelir).
# git+ yerine GitHub tarball'ı kullanıyoruz → slim imajda 'git' kurmaya gerek kalmaz.
# Gömülü veri (data/facets.json) hatch force-include ile wheel'e dahil gelir.
RUN pip install --no-cache-dir \
    "https://github.com/muctebadikmen/yoktez-mcp/archive/refs/heads/master.tar.gz"

# Hosted/paylaşılan ortam ayarları
ENV PORT=7860 \
    YOKTEZ_ENABLE_DISK_CACHE=1 \
    YOKTEZ_CACHE_DIR=/tmp/yoktez-cache

EXPOSE 7860

# Streamable HTTP transport, 0.0.0.0:7860, MCP endpoint: /mcp
CMD ["yoktez-mcp-serve"]
