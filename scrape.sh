cd /Users/unger/dev/src/mtnrtripdata/
#source .venv/bin/activate
uv run src/main.py -C local-config.txt scrape > local-log/"output_$(date +'%Y%m%d_%H%M%S')_unger.log"
uv run src/main.py -C local-config.txt scrape --profile https://www.mountaineers.org/members/will-wade > local-log/"output_$(date +'%Y%m%d_%H%M%S')_wade.log"
uv run src/main.py -C local-config.txt scrape --profile https://www.mountaineers.org/members/colin-farrell > local-log/"output_$(date +'%Y%m%d_%H%M%S')_farrell.log"