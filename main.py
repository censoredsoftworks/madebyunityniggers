import discord
from discord import app_commands
import json
from datetime import datetime
from io import StringIO
from typing import List

from src import database
from src import utils
from src import siege_checker

bot = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(bot)
config = json.load(open('config.json'))

serviceList = []
serviceList_2 = []
is_everything_ready = False

async def getServiceName(service_name, is_premium = False, get_real_name = False):
    if get_real_name:
        return service_name.split("_")[0]
    
    if is_premium:
        return f"{service_name}_premium"
    else:
        return f"{service_name}_free"
    
async def updateServices(service_to_add=None):
    global serviceList, serviceList_2
    if service_to_add:
        serviceList_temp = await database.getServices()
        for service in serviceList_temp:
            if service not in serviceList:
                serviceList.append(str(service))
        serviceList.append(service_to_add)

        for service in serviceList:
            service = await getServiceName(service, get_real_name=True)
            if service not in serviceList_2:
                serviceList_2.append(service)

        return serviceList
    else:
        serviceList = await database.getServices()
        for service in serviceList:
            service = await getServiceName(service, get_real_name=True)
            if service not in serviceList_2:
                serviceList_2.append(service)
    return

async def stage_autcom(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    stages = ["Premium", "Free"]
    return [
        app_commands.Choice(name=stage, value=stage)
        for stage in stages if current.lower() in stage.lower()
    ]

async def service_autcom(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    types = serviceList_2
    return [
        app_commands.Choice(name=service, value=service)
        for service in types if current.lower() in service.lower()
    ]

auth = app_commands.Group(name="auth", description="Manage authentication and subscriptions")
cooldown = app_commands.Group(name="cooldown", description="Manage cooldowns")

@bot.event
async def on_ready():
    global is_everything_ready
    tree.add_command(auth)
    tree.add_command(cooldown)
    tree.copy_global_to(guild=discord.Object(id=config["guild-id"]))
    await tree.sync(guild=discord.Object(id=config["guild-id"]))
    await database.init_db()
    
    await updateServices()
    print("Servicelist:", serviceList)
    
    is_everything_ready = True
    print("Logged in as {0.user}".format(bot))

@tree.command(name = "generate", description = "Generate an account of your choice", guild=discord.Object(id=config["guild-id"]))
@app_commands.autocomplete(service=service_autcom)
async def generate(interaction: discord.Interaction, service: str, is_premium: bool=False):
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    theUser = await database.addUser(str(interaction.user.id))
    if theUser['is_blacklisted']:
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description="You're blacklisted from using this service!",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)

    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        if str(theUser['subscription_stage']) != str(config['subscription-stages'][0]):
            resp = await database.has_subscription_left(str(interaction.user.id))
            if not resp and is_premium:
                embed_error = discord.Embed(
                    title=f"Error: No Subscription",
                    description="Your subscription has ran out, if this is a mistake contact an administrator.",
                    color=config['colors']['error']
                )
                return await interaction.response.send_message(embed=embed_error, ephemeral=True)
        else:
            if is_premium:
                embed_error = discord.Embed(
                    title=f"Error: Access Forbidden",
                    description=f"You don't have permission to use this service, verify your subscription status and try again.",
                    color=config['colors']['error']
                )
                return await interaction.response.send_message(embed=embed_error, ephemeral=True)

    if service not in serviceList_2:
        embed_error = discord.Embed(
            title=f"Error: Invalid service",
            description=f"This service (`{service}`) does not exist, make sure you typed it right.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)

    if not any(role_id in config['admin-roles'] for role_id in role_ids) and not interaction.channel_id in config["gen-channels"]:
        channel_list = [f"<#{channel}>" for channel in config["gen-channels"]]
        return await interaction.response.send_message(str(config['messages']['wrongchannel']) + ', '.join(channel_list), ephemeral=True)

    utl_res = await utils.does_user_meet_requirements(interaction.user.roles, config, service)
    if not any(role_id in config['admin-roles'] for role_id in role_ids) and not utl_res:
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)

    rndm_stage = "Premium" if is_premium else "Free"

    _user_cldw = None
    has_cldw = await database.does_user_have_cooldown(interaction.user.id, rndm_stage)
    if not any(role_id in config['admin-roles'] for role_id in role_ids) and not has_cldw:
        _user_cldw = await database.get_role_user_cooldown(interaction, role_ids, is_premium)
        if _user_cldw is not None:
            await database.set_user_cooldown(interaction.user.id, rndm_stage, int(_user_cldw))
    elif has_cldw:
        _data = await database.getCooldownData(interaction.user.id, rndm_stage)
        if _data['stillHasCooldown']:
            embd=discord.Embed(title="Cooldown",description=f':no_entry_sign: {_data["formatedCooldownMsg"]}',color=config['colors']['error'])
            return await interaction.response.send_message(embed=embd, ephemeral=False)
        elif _data['secondsTillEnd'] == 0:
            _user_cldw = await database.get_role_user_cooldown(interaction, is_premium)
            if _user_cldw is not None:
                await database.set_user_cooldown(interaction.user.id, rndm_stage, int(_user_cldw))
    
    real_service_name = await getServiceName(service, is_premium)
    success, account = await database.getAccount(real_service_name)
    if not success:
        if _user_cldw:
            await database.reset_user_cooldown(str(interaction.user.id), rndm_stage)
        return await interaction.response.send_message(f"There is no stock left.", ephemeral=True)
    else:
        try:
            await interaction.response.defer()
            await database.addUser(str(interaction.user.id), did_gen=True)

            email, password = account.split(":")

            embd=discord.Embed(
                title=f"Account Generated",
                description=f"Thank You For Using {interaction.guild.name}'s Generator!\n\n" +
                          f"Account Credentials Below\n\n" +
                          f"Email: {email}\n" +
                          f"Password: {password}\n",
                color=config['colors']['success']
            )

            embd2=discord.Embed(
                title=f"`{service}` generated",
                description=f':incoming_envelope: Check your DMs for the account.\n{"**It might take a second to receive your account!**" if service in config["services-to-check-ubisoft"] else ""}',
                color=config['colors']['success']
            )
            embd2.set_footer(text=config['messages']['footer-msg'],icon_url=interaction.user.display_avatar.url)
            embd2.set_image(url=config["generate-settings"]["gif-img-url"])
            await interaction.followup.send(embed=embd2, ephemeral=False)
            embd.set_footer(text=config['messages']['footer-msg'],icon_url=interaction.user.display_avatar.url)
        except discord.errors.NotFound:
            return await interaction.followup.send(content=f"{interaction.user.mention}, there was an error with your command execution!", ephemeral=True)

    try:
        channel = await interaction.user.create_dm()
        msg = await channel.send(embed=embd)
        
        if service in config['services-to-check-ubisoft']:
            try:
                inform = await siege_checker.getAccountDetails(account)
                if not inform['success']:
                    embd.color = config['colors']['error']
                    embd.add_field(
                        name="Account Information",
                        value='`Failed to retrieve account information!`'
                    )
                else:
                    info = inform['information']
                    if info:
                        embd.add_field(
                            name="Account Information",
                            value=f"・Username: `{info['username']}`\n" +
                                  f"・Level: `{info['level']}`\n" +
                                  f"・Banned: `{info['banned']}`\n",
                            inline=False
                        )
                        
                        embd.add_field(
                            name="Currency",
                            value=f"・Renown: `{info['currency-renown']}`\n" +
                                  f"・Credits: `{info['currency-credits']}`\n",
                            inline=False
                        )

                        linked_platforms = ", ".join(f"`{platform}`" for platform in info['linked_platforms'])
                        ghost_platforms = ", ".join(f"`{platform}`" for platform in info['ghost_linked'])
                        
                        embd.add_field(
                            name="Platforms",
                            value=f"・Linked Platforms: {linked_platforms}\n",
                        inline=False
                    )

                    inventory = info['inventory']
                    embd.add_field(
                        name="Account Inventory",
                        value=(
                            f"・Total Skins: `{info['amount_of_skins']}`\n" +
                            f"・Seasonals: `{inventory.get('Seasonals', 0)}`\n" +
                            f"More Information About This Account [HERE]({info['siegeskinssiteurl']})"
                        ),
                        inline=False
                    )

                embd.set_footer(text=config['messages']['footer-msg'], icon_url=interaction.user.display_avatar.url)
                return await msg.edit(embed=embd)
            except Exception as e:
                print(e)
    except discord.errors.Forbidden:
        await database.addStock(real_service_name, [account], config['remove-capture-from-stock'])
        await database.reset_user_cooldown(str(interaction.user.id), rndm_stage)
        return await interaction.followup.send(content=f"{interaction.user.mention}, couldn't send you a DM, open your DMs!", ephemeral=True)

@tree.command(name = "user", description = "(admin only)", guild=discord.Object(id=config["guild-id"]))
async def usercmd(interaction: discord.Interaction, user: discord.User):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    the_user = await database.addUser(str(user.id))
    if the_user:
        embd=discord.Embed(
            title=f"Found {user.name}",
            description=f"**ID**: `{the_user['user_id']}`\n" +
            f"**Last Gen**: `{the_user['last_time_genned']}`\n" +
            f"**Total Genned**: `{the_user['amount_genned']}`\n" +
            f"**Is Blacklisted**: `{the_user['is_blacklisted']}`\n" +
            f"**Cooldown end**: `{the_user['user_cooldown']}`\n" +
            f"**Sub Time Left**: `{the_user['subscription_time_left']}`\n" +
            f"**Sub Stage**: `{the_user['subscription_stage']}`\n" +
            f"**Role**: `{the_user['role']}`\n\n" +
            f"Notes about user: `{the_user['notes']}`\n",
            color=int(config['colors']['success'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    else:
        embd=discord.Embed(
            title=f"Error getting user!",
            description=f'`This user does not exist in the database.`',
            color=int(config['colors']['error'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=True)

@tree.command(name = "addstock", description = "(admin only)", guilds=[discord.Object(id=config["guild-id"]), discord.Object(id=config["developer-server-id"])])
@app_commands.autocomplete(service=service_autcom)
async def addaccounts(interaction: discord.Interaction, service: str, file: discord.Attachment, is_premium: bool = False, is_silent: bool=True):
    global serviceList

    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)

    if str(interaction.guild.id) not in [str(config['guild-id']), str(config['developer-server-id'])]:
        embed_error = discord.Embed(
            title=f"Error: Invalid Server",
            description=f"This command can't be used in this server.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)

    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    real_name = await getServiceName(service, is_premium)
    if real_name not in serviceList:
        await updateServices(real_name)
    
    try:
        if not str(file.filename).endswith(".txt"):
            return await interaction.response.send_message(f'You can only upload files with .txt extension', ephemeral=True)
    except:
        return await interaction.response.send_message(f'Error when checking file.', ephemeral=True)

    if file.size > config["maximum-file-size"]:
        return await interaction.response.send_message(f'Maximum file size: `{config["maximum-file-size"]} bytes`', ephemeral=True)
    content = await file.read()

    await interaction.response.defer(ephemeral=is_silent)

    filtered_stock = []
    dec_cont = content.decode('utf-8')
    content = str(dec_cont).split("\n")
    for item in content:
        if len(item) > 2:
            filtered_stock.append(item)
    add_cnt,dupe_cnt = await database.addStock(real_name, filtered_stock, config['remove-capture-from-stock'])
    added_acc_embed = discord.Embed(
        title=f"Added stock to `{service}` :gem: ",
        description=f"`{add_cnt}` (skipped `{dupe_cnt}`) {'premium ' if is_premium else ''}accounts have been added to `{service}` service.",
        color=config['colors']['stock']
    )
    added_acc_embed.set_footer(text=config['messages']['footer-msg'],icon_url=interaction.user.display_avatar.url)
    return await interaction.followup.send(embed=added_acc_embed, ephemeral=is_silent)

@tree.command(name = "bulkgen", description = "(admin only)", guild=discord.Object(id=config["guild-id"]))
@app_commands.autocomplete(service=service_autcom)
async def bulkgen(interaction: discord.Interaction, service: str, amount: int, is_premium: bool, is_silent: bool=True):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    if service not in serviceList_2:
        embed_error = discord.Embed(
            title=f"Error: Invalid service",
            description=f"This service (`{service}`) does not exist, make sure you typed it right.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)

    service_name_rl = await getServiceName(service, is_premium)
    success, accounts = await database.getMultipleAccounts(str(service_name_rl), int(amount))
    if not success:
        embed_error = discord.Embed(
            title=f"Error: Out of stock",
            description=f"This service doesn't seem to have enough accounts to generate.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    accounts_in_file = discord.File(fp=StringIO("\n".join([str(account) for account in accounts])), filename=f"{service}-{amount}.txt")
    return await interaction.response.send_message(content=f"Successfully generated `{amount}` accounts for `{service}`", file=accounts_in_file, ephemeral=True)

@tree.command(name = "deleteservice", description = "(admin only)", guild=discord.Object(id=config["guild-id"]))
@app_commands.autocomplete(service=service_autcom)
async def deleteservice(interaction: discord.Interaction, service: str, is_premium: bool=False):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)

    db_res1 = await database.deleteService(await getServiceName(service, is_premium=is_premium))
    if db_res1:
        await updateServices()

    embd=discord.Embed(
        title=f"Delete Service",
        description=f'{"Successfully deleted service" if db_res1 else "Error. Service doesnt exist."}',
        color=int(config['colors']['success']) if db_res1 else int(config['colors']['error'])
    )
    embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=True)

@tree.command(name = "blacklist", description = "(admin only)", guild=discord.Object(id=config["guild-id"]))
async def blacklistuser(interaction: discord.Interaction, user: discord.User, status: bool=None):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    the_user = await database.getUser(str(user.id))
    if the_user:
        bl_status = await database.blacklist_user(str(user.id), status)
        embd=discord.Embed(
            title=f"Blacklist user",
            description=f"{user.mention}'s blacklist status has been changed successfully to `{bl_status}`",
            color=int(config['colors']['success'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    else:
        embd=discord.Embed(
            title=f"Error getting user!",
            description=f'`This user does not exist in the database.`',
            color=int(config['colors']['error'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=True)

@tree.command(name = "setnote", description = "(admin only)", guild=discord.Object(id=config["guild-id"]))
async def setnote(interaction: discord.Interaction, user: discord.User, note: str):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    the_user = await database.getUser(str(user.id))
    if the_user:
        await database.set_user_note(str(user.id), note)
        embd=discord.Embed(
            title=f"Set note",
            description=f"{user.mention}'s note has been changed.",
            color=int(config['colors']['success'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    else:
        embd=discord.Embed(
            title=f"Error getting user!",
            description=f'`This user does not exist in the database.`',
            color=int(config['colors']['error'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=True)

@tree.command(name="stock", description="Get the amount of stock", guild=discord.Object(id=config["guild-id"]))
async def stock(interaction: discord.Interaction):
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)

    await database.addUser(str(interaction.user.id))

    stock = await database.getStock(serviceList)
    if len(stock) <= 0:
        embd = discord.Embed(
            title=f"Stock - 0 services",
            description="There are no services to display",
            color=config["colors"]["stock"],
        )
        embd.set_footer(text=config["messages"]["footer-msg"])
        return await interaction.response.send_message(embed=embd)

    grouped_stock = {}
    for stk in stock:
        service, count = [s.strip() for s in stk.split(":")]
        base_name, _, tier = service.rpartition("_")
        if base_name not in grouped_stock:
            grouped_stock[base_name] = {"free": 0, "premium": 0}
        if tier in grouped_stock[base_name]:
            grouped_stock[base_name][tier] += int(count)

    filtered_stock = []
    for base_name, counts in grouped_stock.items():
        free_count = counts.get("free", 0)
        premium_count = counts.get("premium", 0)
        service_name = await getServiceName(base_name, get_real_name=True)
        filtered_stock.append(
            f"**{service_name}**: Free: `{free_count}`; Premium: `{premium_count}`"
        )

    embd = discord.Embed(
        title=f"Stock - {len(filtered_stock)}",
        description="\n".join(filtered_stock),
        color=config["colors"]["stock"],
    )
    embd.set_footer(text=config["messages"]["footer-msg"])

    return await interaction.response.send_message(embed=embd, ephemeral=config["stock-command-silent"])

@auth.command(name="add", description="Add subscription time to a user")
@app_commands.autocomplete(stage=stage_autcom)
async def add_subscription(interaction: discord.Interaction, user: discord.User, stage: str, time_sec: int, is_silent: bool=False):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    if stage not in ["Premium", "Free"]:
        return await interaction.response.send_message("Subscription stage must be either Premium or Free.", ephemeral=True)

    the_user = await database.getUser(str(user.id))
    if the_user:
        await database.add_subscription(the_user['user_id'], time_sec)
        embd=discord.Embed(
            title=f"Set subscription",
            description=f"{user.mention}'s subscription has been extended by `{time_sec}` seconds.",
            color=int(config['colors']['success'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    else:
        embd=discord.Embed(
            title=f"Error getting user!",
            description=f'`This user does not exist in the database.`',
            color=int(config['colors']['error'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=is_silent)

@auth.command(name="massadd", description="Add subscription time to all users")
@app_commands.autocomplete(stage=stage_autcom)
async def massadd_subscription(interaction: discord.Interaction, stage: str, time_sec: int, is_silent: bool=False):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)
    
    if stage not in ["Premium", "Free"]:
        return await interaction.response.send_message("Subscription stage must be either Premium or Free.", ephemeral=True)
    
    await interaction.response.send_message(content="Updating everyones subscription.. (this might take a while)", ephemeral=is_silent)
    amount_of_ppl = await database.mass_add_subscription(time_sec)
    if amount_of_ppl:
        embd=discord.Embed(
            title=f"Set subscription",
            description=f"`{amount_of_ppl}` people had their subscription extended by `{time_sec}` seconds.",
            color=int(config['colors']['success'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    else:
        embd=discord.Embed(
            title=f"Error extending subscription!",
            description=f'`There were no users with premium subscription.`',
            color=int(config['colors']['error'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.edit_original_response(content=None, embed=embd)

@auth.command(name="view", description="View subscription status")
async def view_subscription(interaction: discord.Interaction, user: discord.User=None, is_silent: bool=False):
    if user:
        role_ids = [role.id for role in interaction.user.roles]
        if not any(role_id in config['admin-roles'] for role_id in role_ids):
            embed_error = discord.Embed(
                title=f"Error: Access Forbidden",
                description=f"You don't have permission to use this command.",
                color=config['colors']['error']
            )
            return await interaction.response.send_message(embed=embed_error, ephemeral=True)
        
        if not is_everything_ready:
            return await interaction.response.send_message("Bot is starting.", ephemeral=True)
        
        await database.has_subscription_left(str(user.id))
        the_user = await database.getUser(str(user.id))
        if the_user:
            expire = f"<t:{str(int(round(float(the_user['subscription_time_left']), 0)))}:R>" if the_user['subscription_time_left'] else '`None`'
            embd=discord.Embed(
                title=f"Viewing {user.name}'s subscription",
                description=f"**Subscription stage**: `{the_user['subscription_stage']}`\n" +
                f"**Expiration**: {expire}\n" +
                f"**Custom Cooldown**: \n* **Free**: `{the_user['custom_cooldown']['Free']}` seconds\n* **Premium**: `{the_user['custom_cooldown']['Premium']}` seconds\n",
                color=int(config['colors']['success'])
            )
            embd.set_footer(text=config['messages']['footer-msg'])
        else:
            embd=discord.Embed(
                title=f"Error getting user!",
                description=f'`This user does not exist in the database.`',
                color=int(config['colors']['error'])
            )
            embd.set_footer(text=config['messages']['footer-msg'])
        
        return await interaction.response.send_message(embed=embd, ephemeral=is_silent)
    else:
        if not is_everything_ready:
            return await interaction.response.send_message("Bot is starting.", ephemeral=True)
        
        await database.has_subscription_left(str(interaction.user.id))
        the_user = await database.addUser(str(interaction.user.id))
        if the_user:
            expire = f"<t:{str(int(round(float(the_user['subscription_time_left']), 0)))}:R>" if the_user['subscription_time_left'] else '`None`'
            embd=discord.Embed(
                title=f"Viewing {interaction.user.name}'s subscription",
                description=f"**Subscription stage**: `{the_user['subscription_stage']}`\n" +
                f"**Expiration**: {expire}\n" +
                f"**Custom Cooldown**: \n* **Free**: `{the_user['custom_cooldown']['Free']}` seconds\n* **Premium**: `{the_user['custom_cooldown']['Premium']}` seconds\n",
                color=int(config['colors']['success'])
            )
            embd.set_footer(text=config['messages']['footer-msg'])
        else:
            embd=discord.Embed(
                title=f"Error getting user!",
                description=f'`This user does not exist in the database.`',
                color=int(config['colors']['error'])
            )
            embd.set_footer(text=config['messages']['footer-msg'])
        
        return await interaction.response.send_message(embed=embd, ephemeral=is_silent)

@auth.command(name="remove", description="Remove subscription from a user")
async def remove_subscription(interaction: discord.Interaction, user: discord.User, is_silent: bool=False):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)

    the_user = await database.getUser(str(user.id))
    if the_user:
        await database.set_subscription(the_user['user_id'], 0, "Free", True)
        embd=discord.Embed(
            title=f"Remove subscription",
            description=f"{user.mention}'s subscription has been removed.",
            color=int(config['colors']['success'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    else:
        embd=discord.Embed(
            title=f"Error getting user!",
            description=f'`This user does not exist in the database.`',
            color=int(config['colors']['error'])
        )
        embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=is_silent)

@cooldown.command(name="set", description="Set cooldown for a user")
@app_commands.autocomplete(stage=stage_autcom)
async def set_cooldown(interaction: discord.Interaction, user: discord.User, stage: str, time_sec: int, is_silent: bool=False):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)

    if stage not in ["Premium", "Free"]:
        return await interaction.response.send_message("Stage must be either Premium or Free.", ephemeral=True)

    await database.set_user_cooldown(str(user.id), stage, time_sec)
    embd=discord.Embed(
        title=f"Set cooldown",
        description=f"{user.mention}'s cooldown has been set to `{time_sec}` seconds for {stage}.",
        color=int(config['colors']['success'])
    )
    embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=is_silent)

@cooldown.command(name="reset", description="Reset cooldown for a user")
@app_commands.autocomplete(stage=stage_autcom)
async def reset_cooldown(interaction: discord.Interaction, user: discord.User, stage: str, is_silent: bool=False):
    role_ids = [role.id for role in interaction.user.roles]
    if not any(role_id in config['admin-roles'] for role_id in role_ids):
        embed_error = discord.Embed(
            title=f"Error: Access Forbidden",
            description=f"You don't have permission to use this command.",
            color=config['colors']['error']
        )
        return await interaction.response.send_message(embed=embed_error, ephemeral=True)
    
    if not is_everything_ready:
        return await interaction.response.send_message("Bot is starting.", ephemeral=True)

    if stage not in ["Premium", "Free"]:
        return await interaction.response.send_message("Stage must be either Premium or Free.", ephemeral=True)

    await database.reset_user_cooldown(str(user.id), stage)
    embd=discord.Embed(
        title=f"Reset cooldown",
        description=f"{user.mention}'s cooldown has been reset for {stage}.",
        color=int(config['colors']['success'])
    )
    embd.set_footer(text=config['messages']['footer-msg'])
    
    return await interaction.response.send_message(embed=embd, ephemeral=is_silent)

bot.run(config['token'])
