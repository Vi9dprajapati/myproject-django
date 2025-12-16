from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from ckeditor.fields import RichTextField

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Course(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_courses', default=1)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    duration = models.IntegerField(blank=True, null=True)  # in weeks
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes', default=1)
    total_questions = models.IntegerField(default=1)
    total_marks = models.IntegerField(default=10)
    time_limit = models.IntegerField(default=30)  # in minutes
    marks_per_question = models.IntegerField(default=1)
    negative_marking = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    text = models.TextField()
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    option_c = models.CharField(max_length=200)
    option_d = models.CharField(max_length=200)
    correct_answer = models.CharField(
        max_length=1,
        choices=[('A', 'Option A'), ('B', 'Option B'), ('C', 'Option C'), ('D', 'Option D')],
        null=True,
        blank=True
    )
    def __str__(self):
        return self.text[:50]


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    department = models.CharField(max_length=255)
    semester = models.IntegerField()
    pass_out_year = models.IntegerField()
    courses = models.ManyToManyField(Course, related_name='students', blank=True)
    image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    # Document locker PIN fields
    pin = models.CharField(max_length=4, blank=True, null=True)
    recovery_password = models.CharField(max_length=16, blank=True, null=True)
    pin_attempts = models.IntegerField(default=5)

    def __str__(self):
        return self.user.username


class Assignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_assignments', default=1)
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    description = models.TextField()
    topic = models.CharField(max_length=200)
    uploaded_at = models.DateTimeField(default=timezone.now)
    year = models.CharField(max_length=10, blank=True, null=True)
    semester = models.CharField(max_length=10, blank=True, null=True)
    subject = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True)
    section = models.CharField(max_length=10, blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)
    upload_type = models.CharField(max_length=20, choices=[('Assignment', 'Assignment'), ('Notes', 'Notes'), ('Question Bank', 'Question Bank'), ('Papers', 'Papers')], default='Assignment')

    def __str__(self):
        return self.topic


class Note(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='notes', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_notes')
    file = models.FileField(upload_to='notes/', blank=True, null=True)
    content_html = models.TextField(default='')
    topic = models.CharField(max_length=200, default='General')
    description = models.TextField(blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    year = models.CharField(max_length=10, blank=True, null=True)
    semester = models.CharField(max_length=10, blank=True, null=True)
    section = models.CharField(max_length=10, blank=True, null=True)
    upload_type = models.CharField(max_length=20, choices=[('Assignment', 'Assignment'), ('Notes', 'Notes'), ('Question Bank', 'Question Bank'), ('Papers', 'Papers'), ('Lab Manual', 'Lab Manual'), ('Presentation', 'Presentation'), ('Syllabus', 'Syllabus'), ('Other', 'Other')], default='Notes')

    def __str__(self):
        return self.topic


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='submissions/', blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Submission by {self.student.username} for {self.assignment.topic}"


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    department = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    unique_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    courses = models.ManyToManyField(Course, related_name='teachers', blank=True)
    image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    # Document locker PIN fields
    pin = models.CharField(max_length=4, blank=True, null=True)
    recovery_password = models.CharField(max_length=16, blank=True, null=True)
    pin_attempts = models.IntegerField(default=5)

    def __str__(self):
        return self.user.username


class QuizAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_attempts")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    score = models.IntegerField()
    total_questions = models.IntegerField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    time_taken = models.IntegerField(default=0)  # in seconds

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} - {self.score}/{self.total_questions}"


class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_answers')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='user_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='user_answers')
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='user_answers', null=True, blank=True)
    answer = models.CharField(max_length=1, choices=[('A', 'Option A'), ('B', 'Option B'), ('C', 'Option C'), ('D', 'Option D')], null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.question.text[:20]} - {self.answer}"


class ResearchPaper(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_research_papers', default=1)
    title = models.CharField(max_length=300)
    authors = models.CharField(max_length=500, help_text="Comma-separated list of authors")
    abstract = RichTextField(blank=True, null=True)
    file = models.FileField(upload_to='research_papers/', blank=True, null=True)
    published_date = models.DateField(blank=True, null=True)
    journal = models.CharField(max_length=200, blank=True, null=True)
    doi = models.CharField(max_length=100, blank=True, null=True, help_text="Digital Object Identifier")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class StudentDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('notes', 'Notes'),
        ('assignment', 'Assignment'),
        ('question-bank', 'Question Bank'),
        ('presentation', 'Presentation'),
        ('project', 'Project'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='student_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.document_type}"

    def get_file_size(self):
        """Return file size in human readable format"""
        if self.file:
            size = self.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return "0 B"


class TeacherDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('notes', 'Notes'),
        ('assignment', 'Assignment'),
        ('question-bank', 'Question Bank'),
        ('presentation', 'Presentation'),
        ('project', 'Project'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teacher_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='teacher_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.document_type}"

    def get_file_size(self):
        """Return file size in human readable format"""
        if self.file:
            size = self.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return "0 B"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Reset token for {self.user.username}"


class Settings(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    def __str__(self):
        return self.key


class TeacherSubjectContent(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('notes', 'Notes'),
        ('question-bank', 'Question Bank'),
        ('lab-manual', 'Lab Manual'),
        ('presentation', 'Presentation'),
        ('papers', 'Papers'),
        ('assignments', 'Assignments'),
        ('syllabus', 'Syllabus'),
        ('other', 'Other'),
    ]

    DEPARTMENT_CHOICES = [
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

    SEMESTER_CHOICES = [
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ]

    SECTION_CHOICES = [
        ('A1', 'A1'),
        ('B1', 'B1'),
        ('C1', 'C1'),
        ('D1', 'D1'),
    ]

    APPROVAL_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_teacher_content')
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    department = models.CharField(max_length=255, choices=DEPARTMENT_CHOICES)
    year = models.IntegerField()
    semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES)
    section = models.CharField(max_length=10, choices=SECTION_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='teacher_content/')
    teacher_name = models.CharField(max_length=255, blank=True, null=True)
    profile_photo = models.ImageField(upload_to='teacher_profiles/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    submission_data = models.TextField(blank=True, null=True)  # For HTML content or additional submission data
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='pending')

    def __str__(self):
        return f"{self.subject} - {self.content_type} ({self.year})"
