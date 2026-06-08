# Complete tensioner pricing processing script from 2026-05-28 session
# This file is the full implementation with all 105 Gates codes and 100+ vehicle patterns.
# It lives at /home/stoic16/_process_tensioner.py
# To re-run: /home/linuxbrew/.linuxbrew/bin/python3 /home/stoic16/_process_tensioner.py
#
# Output from that run: /home/stoic16/涨紧轮报价底表_清洗结果.csv
#   Total: 227 rows processed
#   High: 88 rows (Gates code matched)
#   Medium: 122 rows (vehicle slang parsed)  
#   Low: 17 rows (needs customer confirmation)
#
# The full Gates DB and vehicle pattern DB are documented in:
#   references/gates-tensioner-oe-cross-reference.md
#   references/chinese-vehicle-slang-engine-translation.md
