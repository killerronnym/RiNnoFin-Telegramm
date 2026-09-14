#!/bin/bash
rm -rf '/volume1/@appdata/jellyfin/data/plugins/RiNnoFin Telegramm_1.0.4.56'
mkdir -p '/volume1/@appdata/jellyfin/data/plugins/RiNnoFin Telegramm_1.0.4.57'
python3 -c "import zipfile; zipfile.ZipFile('/tmp/rinnofin-patch/plugin.zip', 'r').extractall('/volume1/@appdata/jellyfin/data/plugins/RiNnoFin Telegramm_1.0.4.57')"
chown -R sc-jellyfin:synocommunity '/volume1/@appdata/jellyfin/data/plugins/RiNnoFin Telegramm_1.0.4.57'
/usr/syno/bin/synopkg restart jellyfin