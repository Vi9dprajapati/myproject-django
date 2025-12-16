from django import forms
from django.contrib.auth.models import User
from .models import Course, Question, Quiz, Note, Assignment, Category, TeacherProfile, StudentProfile, TeacherSubjectContent, StudentDocument, TeacherDocument
from ckeditor.widgets import CKEditorWidget


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'course', 'time_limit', 'marks_per_question', 'negative_marking']


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'image']


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']





class NoteForm(forms.ModelForm):
    content_html = forms.CharField(widget=forms.HiddenInput())
    year = forms.CharField(max_length=10, required=False)
    semester = forms.CharField(max_length=10, required=False)
    section = forms.CharField(max_length=10, required=False)
    upload_type = forms.ChoiceField(choices=[('Assignment', 'Assignment'), ('Notes', 'Notes'), ('Question Bank', 'Question Bank'), ('Papers', 'Papers')], required=False)

    class Meta:
        model = Note
        fields = ['course', 'file', 'content_html', 'topic', 'year', 'semester', 'section', 'upload_type']


class AssignmentForm(forms.ModelForm):
    year = forms.CharField(max_length=10, required=False)
    semester = forms.CharField(max_length=10, required=False)
    subject = forms.ModelChoiceField(queryset=Course.objects.all(), required=False)
    section = forms.CharField(max_length=10, required=False)
    upload_type = forms.ChoiceField(choices=[('Assignment', 'Assignment'), ('Notes', 'Notes'), ('Question Bank', 'Question Bank'), ('Papers', 'Papers')], required=False)

    class Meta:
        model = Assignment
        fields = ['file', 'description', 'topic', 'year', 'semester', 'subject', 'section', 'upload_type']


DEPARTMENT_CHOICES = [
    ('', 'Select Department'),
    # Engineering
    ('Computer Science & Engineering (CSE)', 'Computer Science & Engineering (CSE)'),
    ('Artificial Intelligence & Data Science (AIDS)', 'Artificial Intelligence & Data Science (AIDS)'),
    ('Information Technology (IT)', 'Information Technology (IT)'),
    ('Electronics & Communication Engineering (ECE)', 'Electronics & Communication Engineering (ECE)'),
    ('Electrical Engineering (EE)', 'Electrical Engineering (EE)'),
    ('Mechanical Engineering (ME)', 'Mechanical Engineering (ME)'),
    ('Civil Engineering (CE)', 'Civil Engineering (CE)'),
    ('Chemical Engineering (CHE)', 'Chemical Engineering (CHE)'),
    ('Aerospace Engineering (AE)', 'Aerospace Engineering (AE)'),
    ('Automobile Engineering (AUTO)', 'Automobile Engineering (AUTO)'),
    ('Biomedical Engineering (BME)', 'Biomedical Engineering (BME)'),
    ('Instrumentation Engineering (IE)', 'Instrumentation Engineering (IE)'),
    # Science
    ('Physics (PHY)', 'Physics (PHY)'),
    ('Chemistry (CHEM)', 'Chemistry (CHEM)'),
    ('Mathematics (MATH)', 'Mathematics (MATH)'),
    ('Computer Science (CS)', 'Computer Science (CS)'),
    ('Biology (BIO)', 'Biology (BIO)'),
    # Management
    ('Business Administration (BBA)', 'Business Administration (BBA)'),
    ('Master of Business Administration (MBA)', 'Master of Business Administration (MBA)'),
    ('Finance (FIN)', 'Finance (FIN)'),
    ('Marketing (MKT)', 'Marketing (MKT)'),
    ('HR Management (HR)', 'HR Management (HR)'),
    # Polytechnic
    ('Computer Engineering (CO)', 'Computer Engineering (CO)'),
    ('Mechanical Engineering (ME)', 'Mechanical Engineering (ME)'),
    ('Civil Engineering (CE)', 'Civil Engineering (CE)'),
    ('Electrical Engineering (EE)', 'Electrical Engineering (EE)'),
    ('Electronics Engineering (EX)', 'Electronics Engineering (EX)'),
]




PASS_OUT_YEAR_CHOICES = [
    ('', 'Select Pass-out Year'),
    ('2025', '2025'),
    ('2026', '2026'),
    ('2027', '2027'),
    ('2028', '2028'),
    ('2029', '2029'),
    ('2030', '2030'),
]

class StudentForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput(), label='Password')
    password2 = forms.CharField(widget=forms.PasswordInput(), label='Confirm Password')
    phone = forms.CharField(max_length=15, required=False)
    department = forms.ChoiceField(choices=DEPARTMENT_CHOICES, required=False)
    semester = forms.CharField(max_length=10, required=False)
    pass_out_year = forms.ChoiceField(choices=PASS_OUT_YEAR_CHOICES, required=False)

    class Meta:
        model = StudentProfile
        fields = ['phone', 'department', 'semester', 'pass_out_year']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1']
        )
        student_profile = super().save(commit=False)
        student_profile.user = user
        student_profile.phone = self.cleaned_data.get('phone')
        student_profile.department = self.cleaned_data.get('department')
        student_profile.semester = self.cleaned_data.get('semester')
        student_profile.pass_out_year = self.cleaned_data.get('pass_out_year')
        if commit:
            student_profile.save()
            self.save_m2m()
        return student_profile


class TeacherForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput(), label='Password')
    password2 = forms.CharField(widget=forms.PasswordInput(), label='Confirm Password')
    phone = forms.CharField(max_length=15, required=False)
    department = forms.ChoiceField(choices=DEPARTMENT_CHOICES, required=False)
    name = forms.CharField(max_length=255, required=True)
    unique_id = forms.CharField(max_length=50, required=False)

    class Meta:
        model = TeacherProfile
        fields = ['phone', 'department', 'name', 'unique_id']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1']
        )
        teacher_profile = super().save(commit=False)
        teacher_profile.user = user
        teacher_profile.phone = self.cleaned_data.get('phone')
        teacher_profile.department = self.cleaned_data.get('department')
        teacher_profile.name = self.cleaned_data.get('name')
        teacher_profile.unique_id = self.cleaned_data.get('unique_id')
        if commit:
            teacher_profile.save()
            self.save_m2m()
        return teacher_profile


class TeacherSubjectContentForm(forms.ModelForm):
    teacher_name = forms.CharField(widget=forms.HiddenInput(), required=False)
    submission_data = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter HTML content or additional submission data'}), required=False, label='Submission Data')

    class Meta:
        model = TeacherSubjectContent
        fields = ['content_type', 'department', 'year', 'semester', 'section', 'subject', 'description', 'file', 'teacher_name', 'submission_data']


class StudentDocumentForm(forms.ModelForm):
    document_type = forms.ChoiceField(choices=StudentDocument.DOCUMENT_TYPE_CHOICES, initial='other')

    class Meta:
        model = StudentDocument
        fields = ['file', 'title', 'description', 'document_type']


class TeacherDocumentForm(forms.ModelForm):
    document_type = forms.ChoiceField(choices=TeacherDocument.DOCUMENT_TYPE_CHOICES, initial='other')

    class Meta:
        model = TeacherDocument
        fields = ['title', 'description', 'file', 'document_type']


class PinSetForm(forms.Form):
    pin = forms.CharField(max_length=4, widget=forms.PasswordInput, label='Set PIN (4 digits)')
    confirm_pin = forms.CharField(max_length=4, widget=forms.PasswordInput, label='Confirm PIN')
    recovery_password = forms.CharField(max_length=16, widget=forms.PasswordInput, label='Recovery Password')

    def clean(self):
        cleaned_data = super().clean()
        pin = cleaned_data.get('pin')
        confirm_pin = cleaned_data.get('confirm_pin')
        if pin and confirm_pin and pin != confirm_pin:
            raise forms.ValidationError("PINs do not match.")
        return cleaned_data


class PinVerifyForm(forms.Form):
    pin = forms.CharField(max_length=4, widget=forms.PasswordInput, label='Enter PIN')


class RecoveryForm(forms.Form):
    recovery_password = forms.CharField(max_length=16, widget=forms.PasswordInput, label='Recovery Password')


class ResetCodeForm(forms.Form):
    reset_code = forms.CharField(max_length=50, label='Reset Code')
