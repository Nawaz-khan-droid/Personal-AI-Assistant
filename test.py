import httpx, asyncio  
async def test():  
    r=await httpx.AsyncClient().get('https://api.open-meteo.com/v1/forecast?latitude=19.076&longitude=72.8777&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=1')  
    print(r.json())  
asyncio.run(test())  
