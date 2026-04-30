from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.checkbox import CheckBox
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
import re


class SignInScreen(FloatLayout):
    def __init__(self, **kwargs):
        super(SignInScreen, self).__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        # Set background color
        with self.canvas.before:
            Color(0.95, 0.95, 0.96, 1)  # Light gray background
            self.rect = Rectangle(size=self.size, pos=self.pos)

        # Logo/App Name
        self.logo_label = Label(
            text="MY APP",
            font_size='32sp',
            bold=True,
            color=(0.2, 0.4, 0.8, 1),  # Blue color
            size_hint=(None, None),
            size=(200, 50),
            pos_hint={'center_x': 0.5, 'top': 0.95}
        )
        self.add_widget(self.logo_label)

        # Welcome Text
        self.welcome_label = Label(
            text="Welcome Back!",
            font_size='24sp',
            color=(0.2, 0.2, 0.2, 1),
            size_hint=(None, None),
            size=(200, 40),
            pos_hint={'center_x': 0.5, 'top': 0.85}
        )
        self.add_widget(self.welcome_label)

        # Sign in to continue
        self.sub_label = Label(
            text="Sign in to continue",
            font_size='16sp',
            color=(0.5, 0.5, 0.5, 1),
            size_hint=(None, None),
            size=(200, 30),
            pos_hint={'center_x': 0.5, 'top': 0.78}
        )
        self.add_widget(self.sub_label)

        # Main container for form
        self.form_container = BoxLayout(
            orientation='vertical',
            spacing=15,
            size_hint=(0.85, 0.5),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            padding=[0, 20, 0, 20]
        )

        # Email Field
        email_container = BoxLayout(orientation='vertical', spacing=5)
        email_label = Label(
            text="Email",
            font_size='14sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='left',
            size_hint_y=None,
            height=25
        )
        self.email_input = TextInput(
            hint_text='Enter your email',
            multiline=False,
            size_hint_y=None,
            height=50,
            padding=[15, 10],
            background_normal='',
            background_active='',
            background_color=(1, 1, 1, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            hint_text_color=(0.7, 0.7, 0.7, 1)
        )
        self.email_input.background_color = (1, 1, 1, 1)
        email_container.add_widget(email_label)
        email_container.add_widget(self.email_input)
        self.form_container.add_widget(email_container)

        # Password Field
        password_container = BoxLayout(orientation='vertical', spacing=5)
        password_label = Label(
            text="Password",
            font_size='14sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='left',
            size_hint_y=None,
            height=25
        )
        self.password_input = TextInput(
            hint_text='Enter your password',
            password=True,
            multiline=False,
            size_hint_y=None,
            height=50,
            padding=[15, 10],
            background_normal='',
            background_active='',
            background_color=(1, 1, 1, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            hint_text_color=(0.7, 0.7, 0.7, 1)
        )
        self.password_input.background_color = (1, 1, 1, 1)
        password_container.add_widget(password_label)
        password_container.add_widget(self.password_input)
        self.form_container.add_widget(password_container)

        # Remember me checkbox
        remember_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=30,
            spacing=10
        )
        self.remember_checkbox = CheckBox(
            size_hint=(None, None),
            size=(30, 30),
            active=False
        )
        remember_label = Label(
            text="Remember me",
            font_size='14sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='left'
        )
        remember_container.add_widget(self.remember_checkbox)
        remember_container.add_widget(remember_label)
        remember_container.add_widget(Widget())  # Spacer

        # Forgot password button
        self.forgot_password_btn = Button(
            text="Forgot Password?",
            font_size='14sp',
            size_hint=(None, None),
            size=(150, 30),
            background_color=(0, 0, 0, 0),
            color=(0.2, 0.4, 0.8, 1),
            bold=True
        )
        self.forgot_password_btn.bind(on_press=self.show_forgot_password_popup)
        remember_container.add_widget(self.forgot_password_btn)
        self.form_container.add_widget(remember_container)

        # Sign In Button
        self.signin_btn = Button(
            text="SIGN IN",
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=55,
            background_color=(0.2, 0.4, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        self.signin_btn.bind(on_press=self.validate_login)
        self.form_container.add_widget(self.signin_btn)

        # Sign Up Link
        signup_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=40
        )
        signup_label = Label(
            text="Don't have an account?",
            font_size='14sp',
            color=(0.5, 0.5, 0.5, 1)
        )
        self.signup_btn = Button(
            text="Sign Up",
            font_size='14sp',
            size_hint=(None, None),
            size=(100, 30),
            background_color=(0, 0, 0, 0),
            color=(0.2, 0.4, 0.8, 1),
            bold=True
        )
        self.signup_btn.bind(on_press=self.show_signup_popup)
        signup_container.add_widget(signup_label)
        signup_container.add_widget(self.signup_btn)
        self.form_container.add_widget(signup_container)

        self.add_widget(self.form_container)

        # Error label
        self.error_label = Label(
            text="",
            font_size='14sp',
            color=(1, 0.3, 0.3, 1),
            size_hint=(0.85, None),
            height=30,
            pos_hint={'center_x': 0.5, 'top': 0.25}
        )
        self.add_widget(self.error_label)

        # Bind for responsive design
        self.bind(size=self.update_rect)

    def update_rect(self, *args):
        self.rect.size = self.size
        self.rect.pos = self.pos

    def validate_login(self, instance):
        email = self.email_input.text.strip()
        password = self.password_input.text.strip()

        # Clear previous error
        self.error_label.text = ""

        # Validation
        if not email:
            self.error_label.text = "Please enter your email"
            return

        if not self.is_valid_email(email):
            self.error_label.text = "Please enter a valid email"
            return

        if not password:
            self.error_label.text = "Please enter your password"
            return

        if len(password) < 6:
            self.error_label.text = "Password must be at least 6 characters"
            return

        # Simulate login process
        self.show_loading_popup()

    def is_valid_email(self, email):
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return re.match(pattern, email) is not None

    def show_loading_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text="Signing in...", font_size='16sp'))

        progress_bar = ProgressBar(max=100, size_hint_y=None, height=20)
        content.add_widget(progress_bar)

        self.loading_popup = Popup(
            title='',
            content=content,
            size_hint=(0.8, 0.3),
            auto_dismiss=False
        )
        self.loading_popup.open()

        # Simulate login process
        Clock.schedule_once(self.login_successful, 2)

    def login_successful(self, dt):
        self.loading_popup.dismiss()

        # Show success message
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(
            text="Login Successful!",
            font_size='18sp',
            color=(0, 0.5, 0, 1)
        ))
        content.add_widget(Label(
            text=f"Welcome back!\nEmail: {self.email_input.text}",
            font_size='14sp'
        ))

        ok_btn = Button(
            text="OK",
            size_hint_y=None,
            height=50,
            background_color=(0.2, 0.4, 0.8, 1),
            color=(1, 1, 1, 1)
        )

        success_popup = Popup(
            title='',
            content=content,
            size_hint=(0.8, 0.4)
        )
        ok_btn.bind(on_press=success_popup.dismiss)
        content.add_widget(ok_btn)
        success_popup.open()

    def show_forgot_password_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text="Forgot Password", font_size='18sp', bold=True))
        content.add_widget(Label(
            text="Enter your email to reset password:",
            font_size='14sp'
        ))

        email_input = TextInput(
            hint_text='Your email',
            multiline=False,
            size_hint_y=None,
            height=40
        )
        content.add_widget(email_input)

        btn_container = BoxLayout(spacing=10, size_hint_y=None, height=50)
        cancel_btn = Button(text="Cancel", background_color=(0.8, 0.2, 0.2, 1))
        reset_btn = Button(text="Reset", background_color=(0.2, 0.4, 0.8, 1))

        popup = Popup(
            title='',
            content=content,
            size_hint=(0.9, 0.4)
        )

        cancel_btn.bind(on_press=popup.dismiss)
        reset_btn.bind(on_press=lambda x: self.send_reset_email(email_input.text, popup))

        btn_container.add_widget(cancel_btn)
        btn_container.add_widget(reset_btn)
        content.add_widget(btn_container)
        popup.open()

    def send_reset_email(self, email, popup):
        if email and self.is_valid_email(email):
            popup.dismiss()
            self.show_message("Reset email sent!", "Check your inbox for reset instructions.")
        else:
            self.show_message("Error", "Please enter a valid email address.")

    def show_signup_popup(self, instance):
        self.show_message("Sign Up", "Sign up functionality would go here!\nThis is a demo UI.")

    def show_message(self, title, message):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text=message, font_size='14sp'))

        ok_btn = Button(
            text="OK",
            size_hint_y=None,
            height=50,
            background_color=(0.2, 0.4, 0.8, 1)
        )

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.8, 0.4)
        )
        ok_btn.bind(on_press=popup.dismiss)
        content.add_widget(ok_btn)
        popup.open()


class SignInApp(App):
    def build(self):
        self.title = "My App - Sign In"
        return SignInScreen()


if __name__ == '__main__':
    SignInApp().run()