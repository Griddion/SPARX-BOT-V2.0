import os
import sys
from dotenv import load_dotenv, set_key
from groq import Groq, AuthenticationError
from img_encoder import encode_image
import pyautogui as gui
import json
from PySide6.QtGui import QIcon, QFont, QFontDatabase
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QScrollArea, QVBoxLayout, QHBoxLayout, QFrame, QApplication, QLineEdit
import time



# ---------------------------------
# SSL fix
if 'SSL_CERT_FILE' in os.environ:
    del os.environ['SSL_CERT_FILE']
# ---------------------------------



# setup AI client

# information on how to use the bot
info = '''
To answer a question, you can either press the 'ANSWER' button at the bottom of the window or you can press 'a' on your keyboard

To close the bot, use either the X like you would do normally, the 'CLOSE' button on the bottom right or press 'q' on your keyboard

To show deep analysis of the question, you can press the 'DEEP DIVE' button that appears under the answer

You can also just copy the answer and paste it if needed

How the bot works:
- When 'a' or the answer button  is pressed, the popup screen is hidden and a screenshot of the screen is performed
- The screenshot is saved automatically and sent to the AI to answer
- The final answer to the question(s) is then displayed on this popup screen where you can use to answer the question
- You can also toggle by pressing the 'DEEP DIVE' button that appears under the answer

Quick notice:
- It can't control your screen and type or click the answer for you... yet

The bot is quite fast if I do say so myself :)
'''

# system mesage for the AI
system_message = '''
You are a very useful homework assistant for anwering science questions
You will be given an image containing the question
Your task is to answer the question
If there are multiple questions, just give the answer that correspond to each question

RESPOND IN THIS JSON OBJECT FORMAT:
For single question:
{
    "explanation": "step-by-step reasoning", "answer": "final answer"
}

For multiple questions:
{
    "explanation1": "reasoning for Q1", "answer1": "answer to Q1",
    "explanation2": "reasoning for Q2", "answer2": "answer to Q2",
    ...
}

Keep explanations concise but informative
'''

# for resources: get absolute path for all resources
def resource_path(relative_path):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# popup widget
class AnswerWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # get the screen size
        x = gui.size()[0]
        
        # set the app icon and app name
        self.setWindowIcon(QIcon(resource_path('bot.png')))
        self.setWindowTitle('SPARX BOT V2')
        
        # adjust window size and move to top right of screen
        self.resize(750, 500)
        self.move(x - 750, 0)
        
        # define global font for all text in window
        font1 = QFontDatabase.addApplicationFont(resource_path('fonts/Cause-VariableFont_wght.ttf'))
        families1 = QFontDatabase.applicationFontFamilies(font1)
        font_families1 = dict(zip(families1, families1))
        
        self.font = QFont(font_families1['Cause SemiBold'], 20)
        
        # set background colour to very dark blue
        self.setStyleSheet('background-color: #00001A')
        
        # define main layout
        self.main_layout = QHBoxLayout(self)
        
        # define UI elements
        # - answer container: answer button, hover label and answer label
        self.ans_container = QVBoxLayout()
        
        # -- answer button: to answer the question on the screen
        self.ans_button = QPushButton('ANSWER')
        self.ans_button.setFont(self.font)
        self.ans_button.setFixedHeight(50)
        self.ans_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #31E6F5;
                border-radius: 10px;
                background-color: #050510;
                font-size: 15px
            }
            
            QPushButton:hover {
                background-color: #020240;
                font-size: 17px
            }
        """)
        
        # -- label to display info/tip about answer button
        self.ans_hover_label = QLabel('')
        self.ans_hover_label.setFont(self.font)
        self.ans_hover_label.setFixedHeight(30)
        self.ans_hover_label.setStyleSheet('font-size: 15px; font-weight: bold;')
        self.ans_hover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # -- check for answer button signals: hovered or clicked
        self.ans_button.enterEvent = lambda event: self.ans_hover_label.setText('Answer the question on screen')
        self.ans_button.leaveEvent = lambda event: self.ans_hover_label.setText('')
        self.ans_button.clicked.connect(self.answer)
        
        # -- scrollable area for answer field
        self.ans_scroll = QScrollArea()
        self.ans_scroll.setMinimumHeight(350)
        self.ans_scroll.setWidgetResizable(True)
        self.ans_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.ans_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # -- label to display the final snaswer
        self.ans_label = QLabel(
            "Welcome to sparx bot v2.0 \n"
            "Click the 'INFO' button on the bottom left or press 'i' for more info on how to use this"
        )
        self.ans_label.setFont(self.font)
        self.ans_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ans_label.setWordWrap(True)
        self.ans_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ans_label.setStyleSheet('font-size: 25px; font-weight: bold;')
        
        # -- add the label to the scrollable area
        self.ans_scroll.setWidget(self.ans_label)
        
        # - right container: explain button, hover label and explanation label, also contains the close button
        self.right_container = QVBoxLayout()
        
        # -- explanation button: opens up the explantion to the question, not visible at first
        self.explain_button = QPushButton('DEEP DIVE')
        self.explain_button.setFont(self.font)
        self.explain_button.setFixedSize(100, 50)
        self.explain_button.setVisible(False)
        self.explain_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #31E6F5;
                border-radius: 10px;
                background-color: #050510;
                font-size: 15px
            }
            
            QPushButton:hover {
                background-color: #020240;
                font-size: 17px
            }
        """)
        
        # -- label to display info/tip about explain button
        self.explain_hover_label = QLabel('')
        self.explain_hover_label.setFont(self.font)
        self.explain_hover_label.setStyleSheet('font-size: 15px; font-weight: bold;')
        self.explain_hover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # -- check for explain button signals: hovered or clicked
        self.explain_button.enterEvent = self.explain_hover_enter
        self.explain_button.leaveEvent = lambda event: self.explain_hover_label.setText('')
        self.explain_button.clicked.connect(self.show_explanation)
        
        # -- scrollable area for the answer explanation
        self.explain_scroll = QScrollArea()
        self.explain_scroll.setMinimumHeight(400)
        self.explain_scroll.setWidgetResizable(True)
        self.explain_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.explain_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # -- label to display the explanation
        self.explain_label = QLabel()
        self.explain_label.setFont(self.font)
        self.explain_label.setWordWrap(True)
        self.explain_label.setStyleSheet('font-size: 25px; font-weight: bold;')
        self.explain_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # -- add the label to scrollable area and hide at first
        self.explain_scroll.setWidget(self.explain_label)
        self.explain_scroll.setVisible(False)
        
        # -- close button: closes the UI
        self.close_button = QPushButton('CLOSE')
        self.close_button.setFont(self.font)
        self.close_button.setFixedSize(100, 50)
        self.close_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #ED2B2B;
                border-radius: 10px;
                background-color: #050510;
                font-size: 15px
            }
            
            QPushButton:hover {
                background-color: #D60202;
                font-size: 17px
            }
        """)
        
        # -- label to display the info/tip about close button
        self.close_hover_label = QLabel('')
        self.close_hover_label.setFont(self.font)
        self.close_hover_label.setFixedSize(100, 30)
        self.close_hover_label.setStyleSheet('font-size: 15px; font-weight: bold;')
        self.close_hover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # -- check for close button signals: hovered or clicked
        self.close_button.enterEvent = lambda event: self.close_hover_label.setText('Close app')
        self.close_button.leaveEvent = lambda event: self.close_hover_label.setText('')
        self.close_button.clicked.connect(self.close_ui)
        
        # - info container: info button, hover label and info label
        self.info_container = QVBoxLayout()
        
        # -- info button: displays the information guide on how to use the bot
        self.info_button = QPushButton('INFO')
        self.info_button.setFont(self.font)
        self.info_button.setFixedSize(100, 50)
        self.info_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #31E6F5;
                border-radius: 10px;
                background-color: #050510;
                font-size: 15px
            }
            
            QPushButton:hover {
                background-color: #020240;
                font-size: 17px
            }
        """)
        
        # -- label to display info/tip about info button
        self.info_hover_label = QLabel('')
        self.info_hover_label.setFont(self.font)
        self.info_hover_label.setFixedSize(100, 30)
        self.info_hover_label.setStyleSheet('font-size: 15px; font-weight: bold;')
        self.info_hover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # -- check for info button signals: hovered or clicked
        self.info_button.enterEvent = self.info_hover_enter
        self.info_button.leaveEvent = lambda event: self.info_hover_label.setText('')
        self.info_button.clicked.connect(self.toggle_info)
        
        # -- scrollable area for the information guide
        self.info_scroll = QScrollArea()
        self.info_scroll.setMinimumHeight(400)
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.info_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # -- label to display the information
        self.info_label = QLabel(info)
        self.info_label.setFont(self.font)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet('font-size: 20px; font-weight: bold;')
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # -- add the label to scrollable area and hide at first
        self.info_scroll.setWidget(self.info_label)
        self.info_scroll.setVisible(False)
        
        
        # add elements to corresponding containers
        # -- add answer elements and explain button to the answer container
        self.ans_container.addStretch()
        self.ans_container.addWidget(self.ans_scroll)
        self.ans_container.addWidget(self.explain_hover_label)
        self.ans_container.addWidget(self.explain_button, alignment = Qt.AlignmentFlag.AlignCenter)
        self.ans_container.addStretch()
        self.ans_container.addWidget(self.ans_hover_label)
        self.ans_container.addWidget(self.ans_button)
        
        # -- add explain elements and close button to the right container
        self.right_container.addStretch()
        self.right_container.addWidget(self.explain_scroll)
        self.right_container.addStretch()
        self.right_container.addWidget(self.close_hover_label)
        self.right_container.addWidget(self.close_button)
        
        # -- add the information elements to the info container
        self.info_container.addStretch()
        self.info_container.addWidget(self.info_scroll)
        self.info_container.addStretch()
        self.info_container.addWidget(self.info_hover_label)
        self.info_container.addWidget(self.info_button)
        
        # welcome screen elements
        self.welcome_label = QLabel()
        self.welcome_label.setFont(self.font)
        self.api_input = QLineEdit()
        self.api_input.setFont(self.font)
        self.help_button = QPushButton('HELP')
        self.help_button.setFont(self.font)
        self.help_label = QLabel()
        self.help_label.setFont(self.font)
        
        # check if the api key is valid or not
        self.check_api()
    
    # setup the actual answer widget
    def main_setup(self):
        # delete welcome elements
        self.welcome_label.deleteLater()
        self.api_input.deleteLater()
        self.help_button.deleteLater()
        self.help_label.deleteLater()
        
        # set up the AI client
        self.client = Groq(api_key = self.api_key)
        
        # add all containers to the main layout
        self.main_layout.addLayout(self.info_container, 3)
        self.main_layout.addLayout(self.ans_container, 5)
        self.main_layout.addLayout(self.right_container, 3)
    
    # welcome setup: displays a welcome message that requires the user to input their api key if not found
    def welcome_setup(self):
        # welcome label to display welcome message or api invalid message
        self.welcome_label.setWordWrap(True)
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setStyleSheet('font-size: 22px; font-weight: bold;')
        self.welcome_label.setText(
            "Hello there new user, welcome to sparx bot v2.0 \n"
            "Looks like you haven't got access to the bot yet - you'll need your api key \n"
            "If you've got it, just paste it in the box below and you'll be good to go \n"
            "If you have no clue what I'm on about, just click the help button below \n"
        )
        
        # input field for the api key to be typed into or pasted
        self.api_input.setPlaceholderText('paste your api key here')
        self.api_input.setFixedHeight(50)
        self.api_input.setStyleSheet("""
            border: 2px solid #31E6F5;
            border-radius: 10px;
            background-color: #050510;
            font-size: 15px
        """)
        
        # saves the api key to the .env file when enter is pressed
        self.api_input.returnPressed.connect(self.save_api)
        
        # help button to show the help info
        self.help_button.setFixedSize(250, 50)
        self.help_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #31E6F5;
                border-radius: 10px;
                background-color: #050510;
                font-size: 15px
            }
            
            QPushButton:hover {
                background-color: #020240;
                font-size: 17px
            }
        """)
        
        # label to display the help info
        self.help_label.setStyleSheet('font-size: 20px; font-weight: bold;')
        self.help_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.help_label.setWordWrap(True)
        self.help_label.setVisible(False)
        self.help_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.help_label.setText(
            "Go to https://github.com/Griddion/SPARX-BOT-V2.0/tree/main for image step by step \n\n"
            "Otherwise: \n"
            "Step 1 - go to this link: https://console.groq.com/home \n"
            "Step 2 - create an account (this is completely free don't worry) \n"
            "To create an account, you can either use google or just type your email and follow the steps from the email you will recieve from groq \n"
            "Step 3 - after logging in, navigate to the api keys section and click on the create api key button \n"
            "Step 4 - you should see a screen that asks you to name it - you can name it whatever you want, set the expiration to no expiration, then click submit \n"
            "Step 5 - when the api key comes up, copy it immediately as you wont see it again \n"
            "Step 6 - paste the api key on the setup screen"
        )
        
        # checks if the help button is clicked to toggle the help info
        self.help_button.clicked.connect(lambda: self.help_label.setVisible(not self.help_label.isVisible()))
        
        # welcome container: welcome label, api input field, and help button
        self.welcome_container = QVBoxLayout()
        self.welcome_container.addStretch()
        self.welcome_container.addWidget(self.welcome_label)
        self.welcome_container.addStretch()
        self.welcome_container.addWidget(self.api_input)
        self.welcome_container.addStretch()
        self.welcome_container.addWidget(self.help_button, alignment = Qt.AlignmentFlag.AlignCenter)
        
        # add the welcome elements to the main layout
        self.main_layout.addLayout(self.welcome_container)
        self.main_layout.addWidget(self.help_label)
    
    # saves the api key to the .env file
    def save_api(self):
        # retrieve the api key from the api input field
        api = self.api_input.text().strip()
        self.api_input.clear()
        
        # prevents double enter
        if not api:
            return
        
        # add the api ket to the .env file
        set_key('.env', 'GROQ_API_KEY', api)
        load_dotenv(override = True)

        self.welcome_label.setText('checking api key...')
        self.check_api()
    
    # checks validity of the api key
    def check_api(self):
        # load the api key for the LLM
        load_dotenv()
        self.api_key = os.environ.get('GROQ_API_KEY')
        
        # checks if the user is a new user, if so, they'll need to get an api key, also checks validity of api key
        if self.api_key is not None:
            if self.api_key != '':
                validity = self.test_api(self.api_key) 
            else:
                validity = 'INVALID'
            
            if validity == 'VALID':
                self.main_setup()
                
            elif validity == 'INVALID':
                self.welcome_setup()
                self.welcome_label.setText('Api key is invalid \nPlease try again')
                
        else:
            self.welcome_setup()
    
    # test to see if the api key works
    def test_api(self, api):
        try:
            self.welcome_label.setText('checking api key...')
            test_client = Groq(api_key = api)
            
            test_message = test_client.chat.completions.create(
                model = 'meta-llama/llama-4-scout-17b-16e-instruct',
                messages = [
                    {
                        'role': 'user',
                        'content': 'hello there'
                    }
                ]
            )
            
            return 'VALID'
        except AuthenticationError:
            return 'INVALID'
    
    # toggles the bot info button
    def toggle_info(self):
        new_state = not self.info_scroll.isVisible()
        self.info_scroll.setVisible(new_state)
    
    # send the encoded question image to the AI to answer
    def answer_question(self, b64_img):
        answer = self.client.chat.completions.create(
            model = 'meta-llama/llama-4-scout-17b-16e-instruct',
            messages = [
                {
                    'role': 'system',
                    'content': system_message
                },
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': 'answer this question please'
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/png;base64,{b64_img}'
                            }
                        }
                    ]
                }
            ],
            response_format = {'type': 'json_object'}
        )
        
        return json.loads(answer.choices[0].message.content)
    
    # updates the answer label and the explanation label 
    def answer(self):
        # hide the explanation 
        self.explain_scroll.setVisible(False)
        
        # hides the UI to take a screenshot
        self.hide()
        time.sleep(0.5)
        gui.screenshot('question.png')
        
        # encodes the image to base 64 for the image url to be sent to the AI
        b64_img = encode_image('question.png')
        
        # sends the image to the AI
        answer = self.answer_question(b64_img)
        
        # blank explanation and final answer variables that would be updated with the final results from the AI
        explanation = ''
        final_ans = ''
        
        # checks the length of the answer
        length = len(answer)
        
        # retrieves and updates the explanation and answer labels based on the length
        # - 2 means one answer, one explanation
        if length == 2:
            explanation = answer['explanation']
            final_ans = answer['answer']
            
            self.explain_label.setText(f'Explanation to answer: \n{explanation}')
            self.ans_label.setText(f'Answer to question: \n{final_ans}')
        
        # - more than 2 means there are multiple answers
        elif length > 2:
            # retrieve all answers and explanations
            num_ans = len(answer) / 2
            for i in range(int(num_ans)):
                exp = answer[f'explanation{i+1}']
                ans = answer[f'answer{i+1}']
                
                explanation += f'{i+1}) {exp}\n\n'
                final_ans += f'{i+1}) {ans}\n\n'
             
            self.explain_label.setText(f'Explanations: \n{explanation}')
            self.ans_label.setText(f'Answers: \n{final_ans}')
        
        self.show()
        self.explain_button.setVisible(True)
    
    def explain_hover_enter(self, event):
        if self.explain_scroll.isVisible(): 
            self.explain_hover_label.setText('Hide explanation')
        else: 
            self.explain_hover_label.setText('Show explanation')

    def info_hover_enter(self, event):
        if self.info_scroll.isVisible(): 
            self.info_hover_label.setText('Hide info')
        else: 
            self.info_hover_label.setText('Show info')
    
    # toggles the explanation area
    def show_explanation(self):
        new_state = not self.explain_scroll.isVisible()
        self.explain_scroll.setVisible(new_state)
    
    # closes the UI
    def close_ui(self):
        self.ans_label.setText('bye bye :)')
        self.explain_button.setVisible(False)
        self.explain_label.setVisible(False)
        self.ans_button.setVisible(False)
        self.info_button.setVisible(False)
        self.info_scroll.setVisible(False)
        self.close_button.setVisible(False)
        
        QTimer.singleShot(500, self.close)
    
    # checks for keyboard key presses: shortcuts to pressing the buttons on the UI
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_I:
            self.toggle_info()
        if event.key() == Qt.Key.Key_A:
            self.answer()
        if event.key() == Qt.Key.Key_Q:
            self.close_ui()
        
        super().keyPressEvent(event)

    
    
if __name__ == '__main__':
    app = QApplication()
    window = AnswerWidget()
    
    window.show()
    
    app.exec()
    
