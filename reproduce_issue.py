from ytmusicapi import YTMusic, setup
import json
import os

headers_json = """{
  "accept": "*/*",
  "authorization": "SAPISIDHASH 1770800581_ce26cc954650f02bc817168928d86e60af567fc3_u SAPISID1PHASH 1770800581_ce26cc954650f02bc817168928d86e60af567fc3_u SAPISID3PHASH 1770800581_ce26cc954650f02bc817168928d86e60af567fc3_u",
  "content-type": "application/json",
  "x-goog-authuser": "0",
  "x-origin": "https://music.youtube.com",
  "cookie": "YSC=nDoNgdhsrcE; LOGIN_INFO=AFmmF2swRQIgKRiJnTzSvC9K-RHxouI6ytDBUjyt54c1e0crDWrMgOICIQDfTQvUIGaQ_3GiV964HHNCKfrmgC0e3FVOXtmHJQK2Rw:QUQ3MjNmeXdyT1FzUHZkTTIyWGh2UkVROUNsM0tVWmRhRnc1OERsYlMwZGR6eHNCX0JPZ19KZ1hOQXlPdjBsQUx5bFM5c045cHlhNWppTE9ZRWdVbE9MQ1VSS3NVUTM0a2hhQ3JQWTNfNzdCbmdDREFZRVpxUXdiOVY2Rl93LWFGM2wyM1NOYmFmRmJEM1BEUjdIR2Nnc2xrZDZud2tTX3ZB; VISITOR_INFO1_LIVE=DV5F3XdANAI; _gcl_au=1.1.704650408.1763975281; wide=1; HSID=ADKJLcmLbY9J7663I; SSID=AVWaVyoAhPPJ-1sfq; APISID=BXsDOM86E0fbUlHl/A0Fk7EeCbY7pZNpIQ; SAPISID=1AGsan0Lu5brN8wl/ADbhV2Y66MKgt-FF2; __Secure-1PAPISID=1AGsan0Lu5brN8wl/ADbhV2Y66MKgt-FF2; __Secure-3PAPISID=1AGsan0Lu5brN8wl/ADbhV2Y66MKgt-FF2; SID=g.a0006giotBNn2lwPJom-gAQbCfhYQxDGxaXqa6vJfYyP1s8pvsLgLX7ncCy-Fxw1L73Nc-3NfwACgYKASASARMSFQHGX2MiPBrM4gk8TTfGWSAV25JIRBoVAUF8yKpSgp7-FANZMCi2IfsZmkPq0076; __Secure-1PSID=g.a0006giotBNn2lwPJom-gAQbCfhYQxDGxaXqa6vJfYyP1s8pvsLgb5e_3lg9La7bd6qA-97vGAACgYKARUSARMSFQHGX2MimyZzx8acH_RaU29yTj0gxRoVAUF8yKqJlLQl6mSaJQCj7obo2-400076; __Secure-3PSID=g.a0006giotBNn2lwPJom-gAQbCfhYQxDGxaXqa6vJfYyP1s8pvsLg9TEaKg7sFSGtd5E9JvVwAAACgYKAeQSARMSFQHGX2MihOcr1vb34dsSnWMqraSHbBoVAUF8yKpwdgHtaax70-UGImlc8umT0076; __Secure-ROLLOUT_TOKEN=CJHs35S2g9e7SRDNpKCAuIqRAxiguJWv1M6SAw%3D%3D; VISITOR_PRIVACY_METADATA=CgJJRBIEGgAgbQ%3D%3D; PREF=f6=40000080&repeat=NONE&tz=Asia.Jakarta&f5=30000&f7=100&autoplay=true; __Secure-1PSIDTS=sidts-CjQB7I_69KUjcdUrjOhrkOziuRDiEy99tzMxRwMoSzAH-AtlhWaC8pDlSTT-5ADNjA2ZxiaEEAA; __Secure-3PSIDTS=sidts-CjQB7I_69KUjcdUrjOhrkOziuRDiEy99tzMxRwMoSzAH-AtlhWaC8pDlSTT-5ADNjA2ZxiaEEAA; CONSISTENCY=AAsGu9mZEdntTvV1SLFXDJc1Vj7KbgspwMFJE5lPt74zzv1w6tjYf_HwaMnqIiQ-Oc4tVQVbrNVAz_ogn01zXiJAMjKl83Jr5MlyUG_emLZmmguf_ktke_qLrs4jN5PBGUPhFie9t_ycptmW6X5ywExi; SIDCC=AKEyXzVF61tVN-waYGCmnogF58T-FNLhAUNCwZfo6PWsUboTcQaAPwBSvMrVpgfn_KKHbVZ0vQ; __Secure-1PSIDCC=AKEyXzVLMG-Abn0dZxLPDHcWQ4ZK_mkvySNJuTWC95NPV9R1s0CJmVBxkTcDeMxFA6RVpbGUOfU; __Secure-3PSIDCC=AKEyXzXThDIzmGzD3ZPKs8ZhUzYC3Az6UnnRTnElzhV5HGEyIYWv8g6QfGImt6VSCdM7p7xv6j-7"
}"""

print("Testing manual JSON save...")
try:
    # Attempt 2: Manual save
    # Validate JSON first
    json.loads(headers_json)
    
    with open("test_oauth.json", "w") as f:
        f.write(headers_json)
        
    print("Success: test_oauth.json created manually.")
    
    # Verify
    yt = YTMusic("test_oauth.json")
    print("Verification successful.")
    
except Exception as e:
    print(f"Error: {e}")

# Cleanup
if os.path.exists("test_oauth.json"):
    os.remove("test_oauth.json")
