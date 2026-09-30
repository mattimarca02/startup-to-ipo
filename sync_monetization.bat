@echo off
rem Double-click to create/update your game passes and developer products from ShopConfig.
rem Keep Roblox Studio open (not playtesting) so the new IDs go straight into the game.
cd /d "%~dp0"
python sync_monetization.py %*
pause
