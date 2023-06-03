class Users:
    all_users = {}

    def __init__(self, chat_id, user_id, firstname, username):
        self.user_id = user_id
        self.chat_id = chat_id
        self.firstname = firstname
        self.username = username
        self.consent = False
        self.messages = []
        self.balance = 0
        self.voiceMode = True

        # Add the new user to the class variable.
        Users.all_users[chat_id] = self

    def get_voiceMode(self):
        return self.voiceMode

    def set_voiceMode(self, voiceMode):
        self.voiceMode = voiceMode

    def get_consent(self):
        return self.consent

    def set_consent(self, consent):
        self.consent = consent

    def add_message(self, message):
        self.messages.append(message)

    def get_balance(self):
        return self.balance

    def set_balance(self, newCredits):
        self.balance += newCredits

    @classmethod
    def find_user_consent(cls, chat_id):
        user = cls.all_users.get(chat_id)
        if user is not None:
            return user.get_consent()
        else:
            return None