import time, pyotp, requests, pickle, re, json, logging, os

from selenium import webdriver
from selenium.webdriver.common.by import By

DEBUG_SAVEALL = True


def login(cf, pwd, totp):
    logging.info("Performing login dance.")
    options = webdriver.FirefoxOptions()
    options.add_argument("-headless")

    driver = webdriver.Firefox(options=options)
    driver.get(f"{baseurl}/LogInAction.do?codop=loginCittadino")
    driver.find_element(
        By.CSS_SELECTOR, "a[spid-idp-button='#spid-idp-button-small-post']"
    ).click()
    while 1:
        try:
            driver.find_element(
                By.CSS_SELECTOR, "a[spid-idp-button='#spid-idp-button-large-get']"
            ).click()
            driver.find_element(
                By.CSS_SELECTOR, "li[data-idp='https://identity.sieltecloud.it']"
            ).click()
            break
        except:
            pass
    while 1:
        try:
            driver.find_element(By.ID, "username").send_keys(cf)
            driver.find_element(By.ID, "password").send_keys(pwd)
            driver.find_element(By.ID, "autorizza").click()
            break
        except:
            pass
    while 1:
        try:
            driver.find_element(By.CSS_SELECTOR, "a[onclick='useAPP()'] > p").click()
            break
        except:
            pass
    while 1:
        try:
            driver.find_element(By.ID, "password").send_keys(totp.now())
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            driver.find_element(By.ID, "autorizza").click()
            break
        except:
            pass
    while 1:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            break
        except:
            pass
    while 1:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            driver.find_element(By.ID, "indexCittadino")
            break
        except:
            pass

    out = driver.get_cookies()
    driver.close()
    logging.info("Login complete.")
    return out


def set_cookies(cookies, s):
    for cookie in cookies:
        if "httpOnly" in cookie:
            httpO = cookie.pop("httpOnly")
            cookie["rest"] = {"httpOnly": httpO}
        if "expiry" in cookie:
            cookie["expires"] = cookie.pop("expiry")
        if "sameSite" in cookie:
            cookie.pop("sameSite")
        s.cookies.set(**cookie)
    return s


def get_province():
    r = rses.get(f"{baseurl}/indexCittadino.jsp").text
    return re.findall(r'<option value="(\w+)">(.+)<\/option>', r)[0]


def get_availability():
    r = rses.get(
        f"{baseurl}/GestioneDisponibilitaAction.do?codop=getDisponibilitaCittadino"
    ).text

    try:
        date = re.findall(r"<td>(\d+\/\d+\/\d+|\d+-\d+-\d+)", r)[0]
    except:
        if "Non ci sono diponibilità nelle strutture della tua provincia" in r:
            return []
    else:
        if DEBUG_SAVEALL:
            ts = int(time.time())
            os.makedirs(f".debug/{ts}")
            with open(f".debug/{ts}/GestioneDisponibilitaAction.html", "w+") as f:
                f.write(r)

    if date:
        match = re.findall(
            r'headers="descrizione"><a\s+.+href="([A-Za-z.?=&;0-9-]+data=(\d{2}-\d{2}-\d{4}))"\s+.+'
            r'title="Disponibilita">([\sA-Za-z\.]+)<\/a>\s+.+\s+.+'
            r' headers="indirizzo">([\w\+\.\,\s\/\d-]+)<\/td>\s+.+'
            r">(\d+)<\/td>",
            r,
        )

        return match


def get_cookie(nocache=False):
    class NoCacheError(Exception):
        pass

    try:
        if nocache:
            raise NoCacheError()
        with open("session.save", "rb") as f:
            cookies = pickle.load(f)
    except (FileNotFoundError, NoCacheError):
        logging.info("Cookie not valid.")
        cookies = login(cf, pwd, pyotp.parse_uri(totp_uri))
        with open("session.save", "wb") as f:
            pickle.dump(cookies, f)
    set_cookies(cookies, rses)

    try:
        get_province()
    except:
        get_cookie(nocache=True)


def new_alert(name, date, address, n, endp):
    content = (
        f"Disponibilità per {name}\n"
        f"Data: {date}\n"
        f"Indirizzo: {address}\n"
        f"Slot: {n}"
    )
    sta = {"ok": False}
    while sta["ok"] == False:
        resp = requests.get(
            "https://api.telegram.org/bot" + tg_token + "/sendMessage",
            data={
                "chat_id": chat_id,
                "parse_mode": "Markdown",
                "text": content,
                "reply_markup": json.dumps(
                    {
                        "inline_keyboard": [
                            [{"text": "Link", "url": f"{baseurl}/{endp}"}]
                        ]
                    }
                ),
            },
        )
        sta = json.loads(resp.text)
    return sta["result"]["message_id"]


def refresh_alert(name, date, address, n, endp):
    al_id = alerts[name]
    content = (
        f"Disponibilità per {name}\n"
        f"Data: {date}\n"
        f"Indirizzo: {address}\n"
        f"Slot: {n}"
    )
    sta = {"ok": False, "error_code": 0}
    while sta["ok"] == False and sta["error_code"] != 400:
        resp = requests.get(
            "https://api.telegram.org/bot" + tg_token + "/editMessageText",
            data={
                "chat_id": chat_id,
                "message_id": al_id,
                "parse_mode": "Markdown",
                "text": content,
                "reply_markup": json.dumps(
                    {
                        "inline_keyboard": [
                            [{"text": "Link", "url": f"{baseurl}/{endp}"}]
                        ]
                    }
                ),
            },
        )
        sta = json.loads(resp.text)


def delete_alert(al_id):
    sta = {"ok": False, "error_code": 0}
    while sta["ok"] == False and sta["error_code"] != 400:
        resp = requests.get(
            "https://api.telegram.org/bot" + tg_token + "/deleteMessage",
            data={"chat_id": chat_id, "message_id": al_id},
        )
        sta = json.loads(resp.text)


alerts = {}

if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    with open("settings.json") as f:
        j = json.load(f)
        baseurl = j["baseurl"]
        cf = j["cf"]
        pwd = j["pwd"]
        totp_uri = j["totp_uri"]
        tg_token = j["tg_token"]
        chat_id = j["chat_id"]
        DEBUG_SAVEALL = j["DEBUG_SAVEALL"]

    try:
        with open("save.pickle", "rb") as f:
            alerts = pickle.load(f)
    except FileNotFoundError:
        pass

    rses = requests.Session()

    while 1:
        try:
            get_cookie()

            # print(rses.cookies)

            prov = get_province()

            avail = get_availability()

            avail = [
                (endp, date, name.strip(), address.strip(), n)
                for endp, date, name, address, n in avail
            ]

            for endp, date, name, address, n in avail:
                if name not in alerts:
                    alerts[name] = new_alert(name, date, address, n, endp)
                    pass
                else:
                    refresh_alert(name, date, address, n, endp)
                    pass

            to_delete = [
                al_id
                for name, al_id in alerts.items()
                if name not in [name for _, _, name, _, _ in avail]
            ]

            alerts = {k: v for k, v in alerts.items() if v not in to_delete}

            for al_id in to_delete:
                delete_alert(al_id)

            n_avail = sum([int(n) for _, _, _, _, n in avail])
            time_to_sleep = n_avail**0.5 or 10

            if n_avail:
                logging.info(
                    f"{n_avail} slots available. Sleeping for {time_to_sleep:.2f} seconds."
                )

            time.sleep(time_to_sleep)

        except KeyboardInterrupt:
            logging.info("Goodbye...")
            break

    with open("save.pickle", "wb") as f:
        pickle.dump(alerts, f)
