import smtplib
import imaplib
import email
import time
import re
import json
from apscheduler.schedulers.background import BackgroundScheduler
from string import printable
import logging

class SMS:
    def __init__(self):
        self.new_message_count = 0
        self.smtp_server = 'smtp.gmail.com'
        self.email_from = '### EMAIL ADDRESS ###'
        self.email_password = '### EMAIL PASSWORD ###'
        self.old_ids=""
        self.contacts = {}
        self.carriers = {}
        self.all_messages = {}
        self.scheduler = ""
        self.startup()
        self.prompt()

    def startup(self):
        try:
            with open('sms/phonebook.json') as f:
                self.contacts = json.load(f)
        except Exception:
            self.contacts = ""

        try:
            with open('sms/carrierlist.json') as f:
                self.carriers = json.load(f)
        except Exception:
            self.carriers = ""

        try:
            with open('sms/messages.json') as f:
                self.all_messages = json.load(f)
        except Exception:
            self.all_messages = ""

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(func=self.new_scan, trigger="interval", seconds=5)
        self.scheduler.start()

        mail = imaplib.IMAP4_SSL(self.smtp_server)
        print(mail.login(self.email_from, self.email_password))
        print(mail.select('inbox'))
        _, ids = mail.search(None, "ALL")
        ids=ids[0].split()
        self.old_ids=ids.copy()

    def prompt(self):
        while self.scheduler.running:
            try:
                if self.new_message_count > 0:
                    print(f"\nNEW MESSAGES ({self.new_message_count})")
                    choice = self.menu()
                    if choice == "1":
                        self.show_messages()
                    elif choice == "2":
                        self.new_message()
                    elif choice == "3":
                        self.add_contact()
                    elif choice == "4":
                        continue
                    else:
                        raise Exception(f" I should not have gotten here. choice - {choice}")
                else:
                    choice = self.menu()
                    if choice == "1":
                        self.show_messages()
                    elif choice == "2":
                        self.new_message()
                    elif choice == "3":
                        self.add_contact()
                    elif choice == "4":
                        print("\n\nLooking for new messages.\nWill notify once a new message comes in.\nctrl+c to quit scan at any time")
                        try:
                            while self.new_message_count == 0:
                                print('.', end="",flush=True)
                                time.sleep(1)
                        except KeyboardInterrupt:
                            continue
                    else:
                        raise Exception(f" I should not have gotten here. choice - {choice}")
            except Exception as e:
                print("\n\n",e)

    def menu(self):
        print()
        input_options = {
            "1":"Show new messages",
            "2":"Send text",
            "3":"Add new contact",
            "4":"Scan for new texts"
        }
        good_choice = False
        while not good_choice:
            print("--------- MENU ----------")
            for option in input_options:
                print(option, ':', input_options[option])
            choice = input("Choice >")
            if choice in input_options.keys():
                return choice
            else:
                print(f"Select 1-{len(input_options)}")
                print()

    def send_text(self,message, number):
        server = smtplib.SMTP_SSL(self.smtp_server, 465)
        server.ehlo()
        print(server.login(self.email_from, self.email_password))
        print(server.sendmail(self.email_from, number, message))

    def new_message(self):
        with open('sms/phonebook.json') as f:
            self.contacts = json.load(f)

        if len(self.contacts) == 0:
            raise Exception("No contacts listed in the phonebook. \nPlease add to send a message.")

        last = len(self.contacts)
        good_choice = False
        contact_choices = {}
        while not good_choice:
            print("\n\n")
            contact_index = 0
            for number, person in self.contacts.items():
                print(f"{contact_index} - {person}")
                contact_choices.update({contact_index:person})
                contact_index = contact_index + 1
            print("_______________________")
            choice = input(f"(0-{last-1}) choose a contact.\n  {last}   to enter a new contact.\n  {last+1}   to return to the main menu.\n>")

            if choice.isdigit():
                choice = int(choice)
                if choice < last:
                    print("\n\n")
                    print("_______________________")
                    print(f"Sending text to {contact_choices[choice]}")
                    print("_______________________")
                    print()
                    message = input("Message to send > ")
                    for phone, alias in self.contacts.items():
                        if alias == contact_choices[choice]:
                            print(message, phone)
                            self.send_text(message, phone)
                            if contact_choices[choice] in self.all_messages.keys():
                                self.all_messages[contact_choices[choice]]['old_messages'].append({"sent_by":"You", "message":message})
                            else:
                                self.all_messages.update({contact_choices[choice]:{"old_messages":[{"sent_by":"You","message":message}],"new_messages":[]}})
                            good_choice = True
                elif choice == last:
                    self.add_contact()
                    self.new_message()
                    good_choice = True
                elif choice == (last+1):
                    print("\n\n")
                    good_choice = True
                else:
                    print("\n\nPlease select a valid option\n")
            else:
                print("\n\nPlease select a valid option")

            with open('sms/messages.json', 'w') as f:
                json.dump(self.all_messages, f)

    def add_contact(self):
        print("\n\n")
        carrier_choices = {}
        carrier_index = 0
        for carrier in self.carriers:
            carrier_choices.update({carrier_index:carrier})
            carrier_index = carrier_index + 1
        for index in carrier_choices:
            print(f"{index} - {carrier_choices[index]}")
        is_good = False
        while not is_good:
            carrier_selection = input(f"________________\nChoose a carrier (0-{len(carrier_choices)-1})\n ctrl+c to go back to main menu.\n>")
            if carrier_selection.isdigit():
                carrier_selection = int(carrier_selection)
                if carrier_selection < len(carrier_choices) and carrier_selection > -1:
                    is_good = True
                #else, no good
            #else, no good

        vendor = self.carriers[carrier_choices[carrier_selection]].lower()
        is_good = False
        while not is_good:
            number = input("Enter phone number > ")
            if number.isdigit() and len(number) == 10:
                is_good = True
            else:
                print("Please enter 10 digits without - or ()")
        phone_vendor = f"{number}{vendor}"

        is_good = False
        while not is_good:
            is_good = True
            name = input("Contact Name > ")
            for person in self.contacts:
                if self.contacts[person].lower() == name.lower():
                    is_good = False
                    print("Contact name already used\n")


        self.all_messages.update({name:{"old_messages":[],"new_messages":[]}})
        self.contacts.update({phone_vendor:name})

        with open('sms/messages.json', 'w') as f:
            json.dump(self.all_messages, f)

        with open('sms/phonebook.json', 'w') as f:
                json.dump(self.contacts, f)

    def read_text(self,message):
        for part in message.walk():
            ctype = part.get_content_type()
            if ctype in ["text/plain"]:
                message = (part.get_payload(decode=True))
                return message.decode()

    def new_scan(self):
        mail = imaplib.IMAP4_SSL(self.smtp_server)
        mail.login(self.email_from, self.email_password)
        mail.select('inbox')#this refreshes your inbox
        _, ids = mail.search(None, "ALL")
        ids=ids[0].split()
        #print(ids)
        if len(ids)!=len(self.old_ids):
            for id in ids:
                if id not in self.old_ids:
                    message=email.message_from_bytes(mail.fetch(id, '(RFC822)')[1][0][1])
                    text=self.read_text(message)
                    text = ''.join(char for char in text if char in printable)
                    reply_from = message.get("from")                        
                    if reply_from in self.contacts.keys():
                        #print(phonebook[reply_from], '-', text)
                        person = self.contacts[reply_from]
                    else:
                        #print(message.get("from"), text)
                        person = message.get("from")
                        self.contacts.update({person:person})
                        with open('sms/phonebook.json', 'w') as f:
                            json.dump(self.contacts,f)
                    
                    with open('sms/messages.json')as f:
                        self.all_messages = json.load(f)

                    if person in self.all_messages.keys():
                        self.all_messages[person]["new_messages"].append(text)
                    else:
                        self.all_messages.update({person:{"old_messages":[], "new_messages":[text]}})
                    self.new_message_count = self.new_message_count + 1
                    with open('sms/messages.json', 'w') as f:
                        json.dump(self.all_messages, f)
                    
        self.old_ids=ids
        
    def reply_check(self):
        good_choice = False
        while not good_choice:
            choice = input("Reply?(y/n)")
            if choice.lower() == 'y':
                good_choice = True
                return choice.lower()
            elif choice.lower() == 'n':
                good_choice = True
                return choice.lower()
            else:
                print('Y/N')
                print()

    def show_messages(self):
        print()
        print()

        with open('sms/messages.json') as f:
            self.all_messages = json.load(f)
        
        people_list = []
        if len(self.all_messages) > 0:
            for person in self.all_messages:
                people_list.append(person)
                if len(self.all_messages[person]['new_messages']) > 0:
                    print(f"{people_list.index(person)} - {person} ({len(self.all_messages[person]['new_messages'])} unread messages)")
                else:
                    print(f"{people_list.index(person)} - {person}")
            
            good_choice = False
            while not good_choice:
                choice = input(f"   (0-{len(people_list)-1}) {len(people_list)} to return to main menu. >")
                if choice.isdigit():
                    choice = int(choice)
                    if choice == len(people_list):
                        return
                    elif choice > len(people_list):
                        print()
                    else:
                        good_choice = True
                else:
                    print()
            print()
            print()
            print()
            print(f"------- {people_list[choice]} -------")
            old_messages = self.all_messages[people_list[choice]]['old_messages']
            new_messages = self.all_messages[people_list[choice]]['new_messages']
            for item in old_messages:
                print(f"{item['sent_by']} - {item['message']}")
            
            if len(new_messages) > 0:
                for item in new_messages:
                    print(f"{people_list[choice]} - {item}        (new)")
                    self.all_messages[people_list[choice]]['old_messages'].append({"sent_by":people_list[choice], "message":item})
                    self.new_message_count = self.new_message_count - 1
                
                print(person, people_list[choice])

                self.all_messages[people_list[choice]]['new_messages'].clear()

                with open('sms/messages.json', 'w') as f:
                    json.dump(self.all_messages, f)
                
                reply_choice = self.reply_check()
                if reply_choice == 'y':
                    message = input("Message > ")
                    for phone, alias in self.contacts.items():
                        if alias == people_list[choice]:
                            self.send_text(message, phone)
                            self.all_messages[people_list[choice]]['old_messages'].append({"sent_by":"You", "message":message})
                #else, user does not want to respond, do_nothing()
                
                with open('sms/messages.json', 'w') as f:
                    json.dump(self.all_messages, f)
            else:
                reply_choice = self.reply_check()
                if reply_choice == 'y':
                    message = input("Message > ")
                    for phone, alias in self.contacts.items():
                        if alias == people_list[choice]:
                            self.send_text(message, phone)
                            self.all_messages[people_list[choice]]['old_messages'].append({"sent_by":"You", "message":message})
                #else, user does not want to respond, do_nothing()
                
                with open('sms/messages.json', 'w') as f:
                    json.dump(self.all_messages, f)
        else:
            print('You have no messages. Gotta send some to get some.')

def main():
    try:
        SMS()
    except KeyboardInterrupt:
        print("\nBye")
    except Exception as e:
        print(logging.exception(e))
                    
if __name__=="__main__":main()