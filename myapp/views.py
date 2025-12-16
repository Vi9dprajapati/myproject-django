from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from .models import Course, Question, StudentProfile, Assignment, Note, Quiz, QuizAttempt, Category, Submission, TeacherProfile, ResearchPaper, UserAnswer, TeacherSubjectContent, PasswordResetToken, StudentDocument, TeacherDocument
from .forms import CourseForm, NoteForm, AssignmentForm, CategoryForm, TeacherForm, StudentForm, TeacherSubjectContentForm
from .utils import classifier
import logging
import fitz  # PyMuPDF
from docx import Document
from weasyprint import HTML
from io import BytesIO
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import json
import requests
import secrets
from django.core.mail import send_mail
from datetime import timedelta


@login_required
def student_dashboard(request):
    courses = Course.objects.all()
    student_profile = None
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        pass

    # Stats
    active_courses = courses.count()
    total_assignments = Assignment.objects.count()
    completed_quizzes = QuizAttempt.objects.filter(student=request.user).count()
    # Simple avg progress - calculate from progress_list
    progress_list = []
    total_progress = 0
    for course in courses:
        # Simple progress logic: assume 50% for demo, or based on attempts
        progress = 50  # Placeholder - can be improved with real data
        course.progress = progress  # Attach progress to course object
        progress_list.append({
            'course_name': course.title,
            'percentage': progress
        })
        total_progress += progress
    avg_progress = total_progress / len(courses) if courses else 0

    stats = {
        'active_courses': active_courses,
        'assignments': total_assignments,
        'completed': completed_quizzes,
        'progress': round(avg_progress, 1)
    }

    # Recent Quiz Results
    recent_attempts = QuizAttempt.objects.filter(student=request.user).order_by('-attempted_at')[:5]
    quizzes = []
    for attempt in recent_attempts:
        quiz = attempt.quiz
        quizzes.append({
            'title': quiz.title,
            'course': quiz.course.title if quiz.course else 'General',
            'score': round((attempt.score / attempt.total_questions) * 100) if attempt.total_questions > 0 else 0
        })

    # Upcoming Deadlines - using Assignments as example
    deadlines = []
    now = timezone.now()
    for assignment in Assignment.objects.all().order_by('uploaded_at')[:5]:
        due_in = 'Due soon'  # Placeholder
        deadlines.append({
            'title': assignment.topic,
            'course': assignment.topic,  # Assume
            'due_in': due_in
        })

    # AI Recommendations - static for now
    recommendations = [
        'Complete your first course to unlock advanced features.',
        'Try attempting a quiz to test your knowledge.',
        'Explore the resources section for additional materials.'
    ]

    context = {
        "courses": courses,
        "student_profile": student_profile,
        "stats": stats,
        "progress_list": progress_list,
        "quizzes": quizzes,
        "deadlines": deadlines,
        "recommendations": recommendations
    }
    return render(request, "student_dashboard.html", context)

def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    course.delete()
    messages.success(request, 'Course deleted successfully!')
    return redirect("admin_dashboard")  # delete hone ke baad admin dashboard par redirect hoga

@csrf_protect
def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")

        if name and description:
            course.title = name
            course.description = description
            course.save()
            messages.success(request, 'Course updated successfully!')
            return redirect("admin_dashboard")  # update hone ke baad admin dashboard par bhej do

    return render(request, "edit_course.html", {"course": course})

@login_required
@csrf_protect
def add_category(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            Category.objects.get_or_create(name=name)
            messages.success(request, 'Category added successfully!')
        return redirect("add_course")  # redirect back to add_course

    return redirect("add_course")

@csrf_protect
def add_course(request):
    categories = Category.objects.all()
    if request.method == "POST":
        course_name = request.POST.get("course_name")
        description = request.POST.get("description")
        category_id = request.POST.get("category")
        duration = request.POST.get("duration")
        course_file = request.FILES.get("course_file")

        category = None
        if category_id:
            try:
                category_id_int = int(category_id)
                category = Category.objects.get(id=category_id_int)
            except (ValueError, Category.DoesNotExist):
                pass

        if course_name and description:
            course = Course.objects.create(title=course_name, description=description, category=category, duration=duration)
            if course_file:
                # Assuming Course model has file field, but it doesn't; for now, just save file to media
                from django.core.files.storage import FileSystemStorage
                fs = FileSystemStorage()
                filename = fs.save(f'courses/{course_file.name}', course_file)
                # Note: Course model needs file field to store this; add later if needed
            messages.success(request, 'Course added successfully!')
            return redirect("admin_dashboard")  # success ke baad admin dashboard par bhej do

    context = {"categories": categories}
    return render(request, "add_course.html", context)

@login_required
@csrf_protect
def edit_profile(request):
    user = request.user

    # Determine user type
    try:
        student_profile = StudentProfile.objects.get(user=user)
        user_type = 'student'
        profile = student_profile
    except StudentProfile.DoesNotExist:
        try:
            teacher_profile = TeacherProfile.objects.get(user=user)
            user_type = 'teacher'
            profile = teacher_profile
        except TeacherProfile.DoesNotExist:
            # If neither profile exists, redirect to dashboard
            messages.error(request, 'Profile not found. Please contact administrator.')
            return redirect('student_dashboard')

    if request.method == 'POST':
        # Update User model fields
        user.username = request.POST.get('username', user.username)
        user.email = request.POST.get('email', user.email)
        user.save()

        if user_type == 'student':
            # Update StudentProfile fields
            profile.email = request.POST.get('email', profile.email)
            profile.phone = request.POST.get('phone', profile.phone)
            profile.department = request.POST.get('department', profile.department)

            # Update User first_name as name
            user.first_name = request.POST.get('name', user.first_name)

            # Handle integer fields safely
            semester_val = request.POST.get('semester')
            if semester_val and semester_val.isdigit():
                profile.semester = int(semester_val)

            pass_out_year_val = request.POST.get('pass_out_year')
            if pass_out_year_val and pass_out_year_val.isdigit():
                profile.pass_out_year = int(pass_out_year_val)

        elif user_type == 'teacher':
            # Update TeacherProfile fields
            profile.phone = request.POST.get('phone', profile.phone)
            profile.department = request.POST.get('department', profile.department)
            profile.name = request.POST.get('name', profile.name)
            profile.unique_id = request.POST.get('unique_id', profile.unique_id)

        # Handle image upload for both profiles
        if request.FILES.get('image'):
            # Delete old image if exists
            if profile.image:
                profile.image.delete(save=False)
            profile.image = request.FILES['image']

        profile.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('edit_profile')

    context = {
        'profile': profile,
        'user_type': user_type,
    }
    return render(request, 'edit_profile.html', context)

def logout_view(request):
    logout(request)
    return redirect('login')   # login page pe redirect hoga

@csrf_protect
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        unique_id = request.POST.get("unique_id")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Agar admin hai to admin dashboard bhejo
            if user.is_staff:
                return redirect("admin_dashboard")

            # Check if the user is a teacher
            try:
                teacher_profile = user.teacherprofile
                if unique_id and teacher_profile.unique_id == unique_id:
                    return redirect("teacher_dashboard")
                else:
                    messages.error(request, "Invalid unique ID for teacher login")
                    return render(request, "login.html")
            except TeacherProfile.DoesNotExist:
                # If not a teacher, check if student
                if not unique_id:  # Students don't provide unique_id
                    try:
                        student_profile = StudentProfile.objects.get(user=user)
                        return redirect("student_dashboard")
                    except StudentProfile.DoesNotExist:
                        messages.error(request, "User is not registered as a student")
                        return render(request, "login.html")
                else:
                    messages.error(request, "Unique ID provided but user is not a teacher")
                    return render(request, "login.html")

        else:
            messages.error(request, "Invalid username or password")
            return render(request, "login.html")

    return render(request, "login.html")

def register(request):
    if request.method == "POST":
        user_type = request.POST.get("user_type")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        name = request.POST.get("name")
        department = request.POST.get("department")
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Basic validation - only for student
        required_fields = [user_type, email, phone, name, department, username, password]

        # For student, add additional required fields
        if user_type == "student":
            confirm_password = request.POST.get("confirm_password")
            semester = request.POST.get("semester")
            pass_out_year = request.POST.get("pass_out_year")
            required_fields.extend([confirm_password, semester, pass_out_year])

        if not all(required_fields):
            messages.error(request, "⚠️ All fields are required.")
            return render(request, "register.html")

        # Password match validation for student
        if user_type == "student":
            if password != confirm_password:
                messages.error(request, "⚠️ Passwords do not match.")
                return render(request, "register.html")

        # Check duplicate
        if User.objects.filter(username=username).exists():
            messages.error(request, "⚠️ Username already exists.")
            return render(request, "register.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "⚠️ Email already exists.")
            return render(request, "register.html")

        # Create new user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=name
        )
        user.save()

        # Save profile - only student
        if user_type == "student":
            semester = request.POST.get("semester")
            pass_out_year = request.POST.get("pass_out_year")

            StudentProfile.objects.create(
                user=user,
                email=email,
                phone=phone,
                department=department,
                semester=semester,
                pass_out_year=pass_out_year
            )

        messages.success(request, "✅ Registered successfully! Please login.")
        return redirect("login")

    return render(request, "register.html")

@csrf_protect
def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin_dashboard")

        # Check if the user is a teacher
        try:
            if request.user.teacherprofile:
                return redirect("teacher_dashboard")
        except TeacherProfile.DoesNotExist:
            # If not a teacher, assume student
            # This handles the case where a student is already logged in
            if not request.user.is_staff:
                return redirect("student_dashboard")

    # For unauthenticated users, show the login page.
    return render(request, 'login.html')

@login_required
@csrf_protect
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('student_dashboard')

    courses = Course.objects.all()
    students = User.objects.filter(is_staff=False)
    teachers = TeacherProfile.objects.all()
    assignments = Assignment.objects.all()
    notes = Note.objects.all()
    quizzes = Quiz.objects.all()
    research_papers = ResearchPaper.objects.all()

    if request.method == "POST":
        if "add_course" in request.POST:
            form = CourseForm(request.POST)
            if form.is_valid():
                course = form.save(commit=False)
                course.user = request.user
                course.save()
                return redirect("admin_dashboard")

    context = {
        "courses": courses,
        "students": students,
        "teachers": teachers,
        "assignments": assignments,
        "notes": notes,
        "quizzes": quizzes,
        "research_papers": research_papers,
        "course_form": CourseForm(),
    }
    return render(request, "admin_dashboard.html", context)

@login_required
def teacher_dashboard(request):
    # Check if user is a teacher
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('student_dashboard')

    assigned_courses = teacher_profile.courses.all()
    my_quizzes = Quiz.objects.filter(course__in=assigned_courses)
    my_assignments = Assignment.objects.filter(user=request.user)
    my_notes = Note.objects.filter(user=request.user)

    # Calculate total students across assigned courses
    total_students = 0
    for course in assigned_courses:
        # Count enrolled students (assuming StudentProfile has courses field)
        enrolled_count = StudentProfile.objects.filter(courses=course).count()
        total_students += enrolled_count

    # Calculate avg completion (placeholder logic)
    avg_completion = 0
    if assigned_courses:
        total_progress = 0
        for course in assigned_courses:
            # Placeholder: assume 50% completion for each course
            total_progress += 50
        avg_completion = total_progress / assigned_courses.count()

    # Add detailed course stats: enrolled_count, quiz_count, avg_score (placeholders)
    detailed_courses = []
    for course in assigned_courses:
        quiz_count = Quiz.objects.filter(course=course).count()
        # Placeholder avg_score calculation
        avg_score = 0
        quizzes = Quiz.objects.filter(course=course)
        total_score = 0
        total_attempts = 0
        for quiz in quizzes:
            attempts = QuizAttempt.objects.filter(quiz=quiz)
            total_attempts += attempts.count()
            for attempt in attempts:
                total_score += attempt.score
        avg_score = (total_score / total_attempts) if total_attempts > 0 else 0

        enrolled_count = StudentProfile.objects.filter(courses=course).count()

        detailed_courses.append({
            'course': course,
            'enrolled_count': enrolled_count,
            'quiz_count': quiz_count,
            'avg_score': round(avg_score, 2),
            'is_active': True,  # Placeholder, adjust as needed
        })

    # Recent activities (placeholder - you can implement actual activity tracking)
    recent_activities = [
        {'description': 'Added new quiz to course', 'timestamp': timezone.now()},
        {'description': 'Updated assignment deadline', 'timestamp': timezone.now()},
    ]

    teachers = TeacherProfile.objects.all()

    context = {
        'assigned_courses': assigned_courses,
        'my_quizzes': my_quizzes,
        'my_assignments': my_assignments,
        'my_notes': my_notes,
        'total_students': total_students,
        'recent_activities': recent_activities,
        'avg_completion': round(avg_completion, 2),
        'detailed_courses': detailed_courses,
        'notes_count': my_notes.count(),
        'teachers': teachers,
    }
    return render(request, 'teacher_dashboard.html', context)

@login_required
def teacher_subject_content(request):
    # Check if user is a teacher
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('student_dashboard')

    if request.method == 'POST':
        form = TeacherSubjectContentForm(request.POST, request.FILES, initial={'teacher_name': teacher_profile.name})
        if form.is_valid():
            content = form.save(commit=False)
            content.user = request.user
            # Auto-fill teacher_name and profile_photo from teacher profile
            content.teacher_name = teacher_profile.name
            if teacher_profile.image:
                content.profile_photo.save(teacher_profile.image.name, teacher_profile.image.file, save=False)
            content.approval_status = 'pending'  # Set to pending for admin approval
            content.save()
            messages.success(request, 'Content uploaded successfully and is pending approval!')
            return redirect('teacher_subject_content')
        else:
            messages.error(request, 'Please fill all required fields and select a file.')
    else:
        form = TeacherSubjectContentForm()

    # Get teacher's uploaded contents for manage tab
    teacher_contents = TeacherSubjectContent.objects.filter(user=request.user).order_by('-uploaded_at')

    # Calculate stats for the teacher
    content_stats = {}
    for content in teacher_contents:
        content_type = content.get_content_type_display()
        if content_type in content_stats:
            content_stats[content_type] += 1
        else:
            content_stats[content_type] = 1

    # Default stats if no content
    stats = {
        'Notes': content_stats.get('Notes', 0),
        'Question_Banks': content_stats.get('Question Bank', 0),
        'Lab_Manuals': content_stats.get('Lab Manual', 0),
        'Papers': content_stats.get('Papers', 0),
        'Assignments': content_stats.get('Assignments', 0),
        'Presentations': content_stats.get('Presentation', 0),
        'Syllabus': content_stats.get('Syllabus', 0),
    }

    # Calculate additional stats
    total_uploads = teacher_contents.count()
    total_students = StudentProfile.objects.filter(department=teacher_profile.department).count()
    total_subjects = teacher_contents.values('subject').distinct().count()

    # Render the teacher subject content template
    context = {
        'teacher_contents': teacher_contents,
        'form': form,
        'stats': stats,
        'teacher_profile': teacher_profile,
        'total_uploads': total_uploads,
        'total_students': total_students,
        'total_subjects': total_subjects,
    }
    return render(request, 'teacher_subject_content.html', context)

@login_required
def delete_teacher_content(request, content_id):
    # Check if user is a teacher
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('student_dashboard')

    content = get_object_or_404(TeacherSubjectContent, id=content_id, user=request.user)
    if request.method == 'POST':
        content.delete()
        messages.success(request, 'Content deleted successfully!')
        return redirect('teacher_subject_content')
    return render(request, 'confirm_delete.html', {'object': content, 'type': 'content'})

@login_required
@csrf_protect
def edit_teacher_content(request, content_id):
    # Check if user is a teacher
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('student_dashboard')

    content = get_object_or_404(TeacherSubjectContent, id=content_id, user=request.user)
    if request.method == 'POST':
        form = TeacherSubjectContentForm(request.POST, request.FILES, instance=content)
        if form.is_valid():
            form.save()
            messages.success(request, 'Content updated successfully!')
            return redirect('teacher_subject_content')
    else:
        form = TeacherSubjectContentForm(instance=content)
    return render(request, 'edit_teacher_content.html', {'form': form, 'content': content})

def courses(request):
    courses = Course.objects.all()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('partials/courses_partial.html', {"courses": courses}, request=request)
        return HttpResponse(html)

    return render(request, "courses.html", {"courses": courses})

@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    notes = Note.objects.filter(course=course)
    quizzes = Quiz.objects.filter(course=course)
    assignments = Assignment.objects.all()  # Since assignments are not linked to courses, show all

    context = {
        'course': course,
        'notes': notes,
        'quizzes': quizzes,
        'assignments': assignments,
    }
    return render(request, "course_detail.html", context)

def resources(request):
    return render(request, "resources.html")

def about(request):
    return render(request, "about.html")

@login_required
def research_paper(request):
    return render(request, "Research_paper.html")

@login_required
@csrf_protect
def add_quiz(request):
    # Filter courses based on user role
    if request.user.is_staff:
        # Admin can see all courses
        courses = Course.objects.all()
    else:
        # Check if user is a teacher
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            courses = teacher_profile.courses.all()
        except TeacherProfile.DoesNotExist:
            # If not teacher or admin, redirect to student dashboard
            return redirect('student_dashboard')

    if request.method == "POST":
        title = request.POST.get('title')
        description = request.POST.get('description')
        total_marks = request.POST.get('total_marks')
        time_limit = request.POST.get('time_limit')
        course_id = request.POST.get('course')
        questions_data = request.POST.get('questions')

        if title and description and course_id:
            course = get_object_or_404(Course, id=course_id)
            # Ensure the course is accessible to the user
            if course not in courses:
                messages.error(request, 'You do not have permission to add quiz to this course.')
                return render(request, "add_quiz_form.html", {"courses": courses})

            quiz = Quiz.objects.create(
                title=title,
                description=description,
                course=course,
                time_limit=time_limit or 0,
                marks_per_question=total_marks or 1,
                total_questions=0
            )

            if questions_data:
                try:
                    questions = json.loads(questions_data)
                    for q in questions:
                        Question.objects.create(
                            quiz=quiz,
                            text=q['text'],
                            option_a=q['options']['A'],
                            option_b=q['options']['B'],
                            option_c=q['options']['C'],
                            option_d=q['options']['D'],
                            correct_answer=q['correct']
                        )
                    quiz.total_questions = len(questions)
                    quiz.save()
                except json.JSONDecodeError:
                    pass  # Handle error if needed

            messages.success(request, 'Quiz added successfully!')
            # Redirect based on user role
            if request.user.is_staff:
                return redirect("admin_dashboard")
            else:
                return redirect("teacher_dashboard")
        else:
            messages.error(request, 'Please fill all required fields.')
    return render(request, "add_quiz_form.html", {"courses": courses})

@login_required
@csrf_protect
def edit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method == "POST":
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            return redirect("admin_dashboard")
    else:
        form = QuizForm(instance=quiz)
    return render(request, "add_quiz_form.html", {"form": form})

@login_required
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.delete()
    return redirect("admin_dashboard")

@login_required
@csrf_protect
def attempt_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all()
    if request.method == "POST":
        score = 0
        total = questions.count()
        user_answers = []
        for question in questions:
            selected = request.POST.get(f'question_{question.id}')
            is_correct = selected == question.correct_answer if selected else False
            if is_correct:
                score += 1
            user_answers.append(UserAnswer(
                user=request.user,
                quiz=quiz,
                question=question,
                answer=selected if selected else None,
                is_correct=is_correct
            ))
        # Calculate time taken (assuming quiz started at page load, but for simplicity, set to time_limit)
        time_taken = quiz.time_limit * 60  # in seconds
        attempt = QuizAttempt.objects.create(student=request.user, quiz=quiz, score=score, total_questions=total, time_taken=time_taken)
        for ua in user_answers:
            ua.attempt = attempt
        UserAnswer.objects.bulk_create(user_answers)
        return redirect("scoreboard")
    return render(request, "attempt_quiz.html", {"quiz": quiz, "questions": questions})

@login_required
def scoreboard(request):
    attempts = QuizAttempt.objects.filter(student=request.user).order_by('-attempted_at')
    return render(request, "scoreboard.html", {"attempts": attempts})

@login_required
@csrf_protect
def add_question(request):
    if request.method == "POST":
        quiz_id = request.POST.get('quiz')
        question_text = request.POST.get('question')
        option_a = request.POST.get('option_a')
        option_b = request.POST.get('option_b')
        option_c = request.POST.get('option_c')
        option_d = request.POST.get('option_d')
        correct_answer = request.POST.get('correct_answer')

        quiz = get_object_or_404(Quiz, id=quiz_id)
        Question.objects.create(
            quiz=quiz,
            text=question_text,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_answer=correct_answer
        )
        return redirect("admin_dashboard")

    quizzes = Quiz.objects.all()
    return render(request, "add_quiz.html", {"quizzes": quizzes})

@login_required
def assignments(request):
    assignments = Assignment.objects.all()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('partials/assignments_partial.html', {"assignments": assignments}, request=request)
        return HttpResponse(html)

    return render(request, "assignments.html", {"assignments": assignments})

@login_required
def assignment_detail(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submissions = Submission.objects.filter(assignment=assignment, student=request.user)
    has_submitted = submissions.exists()
    submission = submissions.first() if has_submitted else None

    if request.method == "POST" and not has_submitted:
        file = request.FILES.get('file')
        if file:
            Submission.objects.create(assignment=assignment, student=request.user, file=file)
            messages.success(request, 'Assignment submitted successfully!')
            return redirect('assignment_detail', assignment_id=assignment_id)

    context = {
        'assignment': assignment,
        'submission': submission,
        'has_submitted': has_submitted,
    }
    return render(request, "assignment_detail.html", context)

@login_required
def progress(request):
    # Get progress data for the current user
    courses = Course.objects.all()
    progress_data = []
    for course in courses:
        # Placeholder progress logic: assume 50% for demo
        progress_percentage = 50  # Can be improved with real data
        completed_assignments = 1  # Placeholder
        total_assignments = 2  # Placeholder
        progress_data.append({
            'course': course,
            'progress': progress_percentage,
            'completed': completed_assignments,
            'total': total_assignments
        })

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('partials/progress_partial.html', {"progress_data": progress_data}, request=request)
        return HttpResponse(html)

    return render(request, "student_progress.html", {"progress_data": progress_data})

@login_required
def notes(request):
    # Get enrolled courses for the user
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
        enrolled_courses = student_profile.courses.all()
    except StudentProfile.DoesNotExist:
        enrolled_courses = []

    # Get notes for enrolled courses
    notes = Note.objects.filter(course__in=enrolled_courses).order_by('course__title', 'topic')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('partials/notes_partial.html', {"notes": notes, "enrolled_courses": enrolled_courses}, request=request)
        return HttpResponse(html)

    return render(request, "notes.html", {"notes": notes, "enrolled_courses": enrolled_courses})

@login_required
@csrf_protect
def add_note(request):
    if request.method == "POST":
        form = NoteForm(request.POST, request.FILES)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, 'Note added successfully!')
            return redirect("admin_dashboard")
        else:
            messages.error(request, 'Please fill all required fields.')
    else:
        form = NoteForm()
    return render(request, "notesform.html", {"form": form})

@login_required
@csrf_protect
def edit_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    if request.method == "POST":
        form = NoteForm(request.POST, request.FILES, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, 'Note updated successfully!')
            return redirect("admin_dashboard")
    else:
        form = NoteForm(instance=note)
    return render(request, "edit_note.html", {"form": form, "note": note})

@login_required
def delete_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    note.delete()
    return redirect("admin_dashboard")

@login_required
@csrf_protect
def add_assignment(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.user = request.user
            assignment.save()
            messages.success(request, 'Assignment added successfully!')
            return redirect("admin_dashboard")
        else:
            messages.error(request, 'Please fill all required fields.')
    else:
        form = AssignmentForm()
    return render(request, "assignment_add_form.html", {"form": form})

@login_required
@csrf_protect
def edit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES, instance=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Assignment updated successfully!')
            return redirect("admin_dashboard")
    else:
        form = AssignmentForm(instance=assignment)
    return render(request, "edit_assignment.html", {"form": form, "assignment": assignment})

@login_required
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    assignment.delete()
    return redirect("admin_dashboard")

@login_required
def student_list(request):
    students = User.objects.filter(is_staff=False)
    return render(request, "student_list.html", {"students": students})

@login_required
def all_quiz(request):
    quizzes = Quiz.objects.all()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('partials/quizzes_partial.html', {"quizzes": quizzes}, request=request)
        return HttpResponse(html)

    return render(request, "all_quiz.html", {"quizzes": quizzes})



@csrf_exempt
def ollama_stream(request):
    """
    Stream Ollama responses to the frontend for real-time chat experience.
    """
    if request.method != 'POST':
        def error_generate():
            yield f"data: {json.dumps({'error': 'Method not allowed'})}\n\n"
        return StreamingHttpResponse(
            error_generate(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
            }
        )

    try:
        data = json.loads(request.body)
        prompt = data.get('prompt', '').strip()
        model = data.get('model', 'llama3:latest')

        if not prompt:
            def error_generate():
                yield f"data: {json.dumps({'error': 'No prompt provided'})}\n\n"
            return StreamingHttpResponse(
                error_generate(),
                content_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                }
            )

        def generate():
            try:
                # Check if prompt is "hi" (case insensitive)
                if prompt.lower().strip() == "hi":
                    # Send fixed greeting message as one chunk
                    greeting = "Hi! It's nice to meet you. Is there something I can help you with, or would you like to chat?"
                    yield f"data: {json.dumps({'response': greeting})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

                # Ollama API endpoint for streaming
                ollama_url = "http://localhost:11434/api/generate"

                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": True
                }

                response = requests.post(ollama_url, json=payload, stream=True, timeout=300)

                if response.status_code != 200:
                    yield f"data: {json.dumps({'error': f'Ollama API error: {response.status_code}'})}\n\n"
                    return

                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            if 'response' in chunk and chunk['response'].strip():
                                # Send each response chunk immediately for real-time streaming
                                yield f"data: {json.dumps({'response': chunk['response']})}\n\n"
                            if chunk.get('done', False):
                                # Send completion signal
                                yield f"data: {json.dumps({'done': True})}\n\n"
                                break
                        except json.JSONDecodeError:
                            continue

            except requests.exceptions.RequestException as e:
                yield f"data: {json.dumps({'error': f'Connection error: {str(e)}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Unexpected error: {str(e)}'})}\n\n"

        return StreamingHttpResponse(
            generate(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
            }
        )

    except json.JSONDecodeError:
        def error_generate():
            yield f"data: {json.dumps({'error': 'Invalid JSON'})}\n\n"
        return StreamingHttpResponse(
            error_generate(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
            }
        )
    except Exception as e:
        def error_generate():
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingHttpResponse(
            error_generate(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
            }
        )

# import http
# import httpx
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from decouple import config
# import openai

@login_required
def course_notes(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    notes = Note.objects.filter(course=course).order_by('topic')
    # Group notes by topic
    notes_by_topic = {}
    for note in notes:
        topic = note.topic
        if topic not in notes_by_topic:
            notes_by_topic[topic] = []
        notes_by_topic[topic].append(note)
    context = {
        'course': course,
        'notes_by_topic': notes_by_topic,
    }
    return render(request, "courses_notes.html", context)


@login_required
@csrf_protect
def add_note_to_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Only admins can add notes to courses.'})
    if request.method == "POST":
        topic = request.POST.get('topic')
        content_html = request.POST.get('content_html')
        file = request.FILES.get('file')

        if topic:
            try:
                # If no content_html provided, try to extract from file
                if not content_html and file:
                    file_name = file.name.lower()
                    if file_name.endswith('.pdf'):
                        # Extract text from PDF and convert to HTML
                        doc = fitz.open(stream=file.read(), filetype="pdf")
                        html_content = ""
                        for page in doc:
                            html_content += page.get_text("html")
                        content_html = html_content
                        doc.close()
                    elif file_name.endswith('.docx'):
                        # Extract text from DOCX and wrap in basic HTML
                        doc = Document(file)
                        text_content = ""
                        for para in doc.paragraphs:
                            text_content += para.text + "\n"
                        content_html = f"<p>{text_content.replace('\n', '</p><p>')}</p>"
                    # Reset file pointer for saving
                    file.seek(0)

                note = Note.objects.create(
                    course=course,
                    user=request.user,
                    topic=topic,
                    content_html=content_html or '',  # Store HTML content in content_html
                    file=file
                )
                return JsonResponse({'success': True, 'message': 'Note added successfully!'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error creating note: {str(e)}'})
        else:
            return JsonResponse({'success': False, 'message': 'Topic is required.'}, status=400)
    else:
        form = NoteForm()
    return render(request, "add_note_to_course.html", {"form": form, "course": course})


@login_required
@csrf_exempt
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image = request.FILES['image']
        fs = FileSystemStorage()
        filename = fs.save(f'notes/{image.name}', image)
        image_url = fs.url(filename)
        return JsonResponse({'url': image_url})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def download_note_html_as_pdf(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    if not note.content_html:
        return HttpResponse("No content available for download.", status=404)

    # Generate PDF from HTML content
    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{note.topic}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            p {{ line-height: 1.6; }}
        </style>
    </head>
    <body>
        <h1>{note.topic}</h1>
        {note.content_html}
    </body>
    </html>
    """

    # Create PDF
    pdf_buffer = BytesIO()
    HTML(string=html_string).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)

    # Return PDF as response
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{note.topic}.pdf"'
    pdf_buffer.close()
    return response




@login_required
def view_results(request):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    attempts = QuizAttempt.objects.all().order_by('-attempted_at')
    # Group by quiz and calculate rankings
    quiz_results = {}
    for attempt in attempts:
        quiz_id = attempt.quiz.id
        if quiz_id not in quiz_results:
            quiz_results[quiz_id] = {
                'quiz': attempt.quiz,
                'attempts': []
            }
        quiz_results[quiz_id]['attempts'].append(attempt)

    # Sort attempts by score descending for each quiz
    for quiz_data in quiz_results.values():
        quiz_data['attempts'].sort(key=lambda x: x.score, reverse=True)

    context = {
        'quiz_results': quiz_results
    }
    return render(request, 'view_results.html', context)


# Teacher management views
@login_required
@csrf_protect
def teacher_list(request):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    teachers = TeacherProfile.objects.all()
    return render(request, 'teacher_list.html', {'teachers': teachers})

@login_required
@csrf_protect
def create_teacher(request):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Teacher created successfully!')
            return redirect('teacher_list')
    else:
        form = TeacherForm()
    return render(request, 'create_teacher.html', {'form': form})

@login_required
def delete_teacher(request, teacher_id):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)
    teacher.user.delete()  # This will cascade delete the TeacherProfile
    messages.success(request, 'Teacher deleted successfully!')
    return redirect('teacher_list')

@login_required
@csrf_protect
def reset_teacher_password(request, teacher_id):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        if new_password:
            teacher.user.set_password(new_password)
            teacher.user.save()
            messages.success(request, 'Password reset successfully!')
            return redirect('teacher_list')
    return render(request, 'reset_teacher_password.html', {'teacher': teacher})

@login_required
@csrf_protect
def assign_courses_to_teacher(request, teacher_id):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)
    if request.method == 'POST':
        course_ids = request.POST.getlist('courses')
        teacher.courses.set(Course.objects.filter(id__in=course_ids))
        messages.success(request, 'Courses assigned successfully!')
        return redirect('teacher_list')
    courses = Course.objects.all()
    return render(request, 'assign_courses_to_teacher.html', {'teacher': teacher, 'courses': courses})

# Research Paper views
@login_required
@csrf_protect
def add_research_paper(request):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    if request.method == 'POST':
        title = request.POST.get('title')
        authors = request.POST.get('authors')
        abstract = request.POST.get('abstract')
        file = request.FILES.get('file')
        published_date = request.POST.get('published_date')
        journal = request.POST.get('journal')
        doi = request.POST.get('doi')

        if title and authors:
            ResearchPaper.objects.create(
                user=request.user,
                title=title,
                authors=authors,
                abstract=abstract,
                file=file,
                published_date=published_date,
                journal=journal,
                doi=doi
            )
            messages.success(request, 'Research paper added successfully!')
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Title and authors are required.')
    return render(request, 'add_research_paper.html')
@login_required
@csrf_protect
def edit_research_paper(request, paper_id):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    paper = get_object_or_404(ResearchPaper, id=paper_id)
    if request.method == 'POST':
        paper.title = request.POST.get('title')
        paper.authors = request.POST.get('authors')
        paper.abstract = request.POST.get('abstract')
        if request.FILES.get('file'):
            paper.file = request.FILES.get('file')
        paper.published_date = request.POST.get('published_date')
        paper.journal = request.POST.get('journal')
        paper.doi = request.POST.get('doi')
        paper.save()
        messages.success(request, 'Research paper updated successfully!')
        return redirect('admin_dashboard')
    return render(request, 'edit_research_paper.html', {'paper': paper})
@login_required
def delete_research_paper(request, paper_id):
    if not request.user.is_staff:
        return redirect('student_dashboard')
    paper = get_object_or_404(ResearchPaper, id=paper_id)
    paper.delete()
    messages.success(request, 'Research paper deleted successfully!')
    return redirect('admin_dashboard')


@login_required
def documents(request):
    from .models import StudentDocument, TeacherDocument, Settings

    # Check if user is student or teacher
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        user_type = 'teacher'
        profile = teacher_profile
    except TeacherProfile.DoesNotExist:
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
            user_type = 'student'
            profile = student_profile
        except StudentProfile.DoesNotExist:
            messages.error(request, 'Profile not found.')
            return redirect('student_dashboard')

    # Check if PIN is set
    if not profile.pin:
        return redirect('set_pin')



    if user_type == 'student':
        # Show only student's own documents
        documents = StudentDocument.objects.filter(user=request.user).order_by('-uploaded_at')
    else:
        # Show teacher's documents
        documents = TeacherDocument.objects.filter(user=request.user).order_by('-uploaded_at')

    context = {
        'user_type': user_type,
        'documents': documents,
        'profile': profile,
        'pin_verified': request.session.get('pin_verified', False),
    }
    return render(request, 'documents.html', context)


@login_required
def set_pin(request):
    from .forms import PinSetForm

    try:
        student_profile = StudentProfile.objects.get(user=request.user)
        profile = student_profile
    except StudentProfile.DoesNotExist:
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            profile = teacher_profile
        except TeacherProfile.DoesNotExist:
            messages.error(request, 'Profile not found.')
            return redirect('student_dashboard')

    if request.method == 'POST':
        form = PinSetForm(request.POST)
        if form.is_valid():
            profile.pin = form.cleaned_data['pin']
            profile.recovery_password = form.cleaned_data['recovery_password']
            profile.save()
            messages.success(request, 'PIN and recovery password set successfully!')
            return redirect('verify_pin')
    else:
        form = PinSetForm()

    return render(request, 'set_pin.html', {'form': form})


@login_required
def verify_pin(request):
    from .forms import PinVerifyForm

    try:
        student_profile = StudentProfile.objects.get(user=request.user)
        profile = student_profile
    except StudentProfile.DoesNotExist:
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            profile = teacher_profile
        except TeacherProfile.DoesNotExist:
            messages.error(request, 'Profile not found.')
            return redirect('student_dashboard')

    if request.method == 'POST':
        form = PinVerifyForm(request.POST)
        if form.is_valid():
            entered_pin = form.cleaned_data['pin']
            if entered_pin == profile.pin:
                request.session['pin_verified'] = True
                return redirect('documents')
            else:
                profile.pin_attempts -= 1
                profile.save()
                if profile.pin_attempts <= 0:
                    messages.error(request, 'Too many failed attempts. Use recovery password.')
                    return redirect('recovery')
                messages.error(request, f'Incorrect PIN. {profile.pin_attempts} attempts remaining.')
    else:
        form = PinVerifyForm()

    return render(request, 'verify_pin.html', {'form': form})


@login_required
def recovery(request):
    from .forms import RecoveryForm

    try:
        student_profile = StudentProfile.objects.get(user=request.user)
        profile = student_profile
    except StudentProfile.DoesNotExist:
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            profile = teacher_profile
        except TeacherProfile.DoesNotExist:
            messages.error(request, 'Profile not found.')
            return redirect('student_dashboard')

    if request.method == 'POST':
        form = RecoveryForm(request.POST)
        if form.is_valid():
            entered_recovery = form.cleaned_data['recovery_password']
            if entered_recovery == profile.recovery_password:
                request.session['pin_verified'] = True
                return redirect('documents')
            else:
                messages.error(request, 'Incorrect recovery password.')
    else:
        form = RecoveryForm()

    return render(request, 'recovery.html', {'form': form})


@login_required
def reset_data(request):
    from .models import TeacherDocument, Settings
    from .forms import ResetCodeForm

    try:
        student_profile = StudentProfile.objects.get(user=request.user)
        profile = student_profile
        user_type = 'student'
    except StudentProfile.DoesNotExist:
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            profile = teacher_profile
            user_type = 'teacher'
        except TeacherProfile.DoesNotExist:
            messages.error(request, 'Profile not found.')
            return redirect('student_dashboard')

    # Get reset code from settings
    try:
        reset_setting = Settings.objects.get(key='reset_code')
        reset_code = reset_setting.value
    except Settings.DoesNotExist:
        messages.error(request, 'Reset code not configured.')
        return redirect('documents')

    if request.method == 'POST':
        form = ResetCodeForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['reset_code']
            if entered_code == reset_code:
                # Delete all user data
                if user_type == 'student':
                    Note.objects.filter(user=request.user).delete()
                else:
                    TeacherDocument.objects.filter(user=request.user).delete()
                # Reset PIN and recovery
                profile.pin = None
                profile.recovery_password = None
                profile.pin_attempts = 5
                profile.save()
                # Clear session
                request.session.flush()
                messages.success(request, 'All data deleted. Please set new PIN.')
                return redirect('set_pin')
            else:
                messages.error(request, 'Incorrect reset code.')
    else:
        form = ResetCodeForm()

    return render(request, 'reset_data.html', {'form': form})


@login_required
def upload_student_document(request):
    from .forms import StudentDocumentForm

    if request.method == 'POST':
        form = StudentDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.save()
            messages.success(request, 'Document uploaded successfully!')
            return redirect('documents')
    else:
        form = StudentDocumentForm()

    return render(request, 'upload_student_document.html', {'form': form})


@login_required
def upload_teacher_document(request):
    from .forms import TeacherDocumentForm

    if request.method == 'POST':
        form = TeacherDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.save()
            messages.success(request, 'Document uploaded successfully!')
            return redirect('documents')
    else:
        form = TeacherDocumentForm()

    return render(request, 'upload_teacher_document.html', {'form': form})


@login_required
@csrf_exempt
def predict(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            if not text:
                return JsonResponse({'error': 'No text provided'}, status=400)

            # Log the request in terminal
            print(f"User {request.user.username} requested text classification.")
            print(f"Input Text: {text}")

            # Use the classifier
            category, probabilities = classifier.predict(text)

            # Calculate confidence as max probability
            confidence = int(max(probabilities) * 100)

            # Log the prediction in terminal
            print(f"Prediction: Category={category}, Confidence={confidence}%")

            # Define descriptions for categories (assuming standard categories)
            descriptions = {
                'business': 'This text appears to be related to business, finance, or corporate matters.',
                'entertainment': 'This text seems to be about entertainment, movies, music, or leisure activities.',
                'politics': 'This text discusses political topics, government, or public affairs.',
                'sports': 'This text is about sports, athletics, or competitive events.',
                'tech': 'This text covers technology, science, or innovation topics.',
                'health': 'This text relates to health, medicine, or wellness.',
                'education': 'This text is about education, learning, or academic subjects.',
                'general': 'This text covers general or miscellaneous topics.'
            }

            # Get description, default to general
            description = descriptions.get(category.lower(), 'This text covers general topics.')

            # Format probabilities as percentages
            prob_dict = {}
            # Assuming the model has classes, but since we don't know, use indices
            # For demo, assume classes are ['business', 'entertainment', 'politics', 'sports', 'tech']
            classes = ['business', 'entertainment', 'politics', 'sports', 'tech']
            for i, prob in enumerate(probabilities):
                if i < len(classes):
                    prob_dict[classes[i]] = int(prob * 100)

            return JsonResponse({
                'category': category,
                'confidence': confidence,
                'description': description,
                'probabilities': prob_dict
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def text_classify(request):
    return render(request, "text_classify.html")

import secrets
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = None

        # Check if email belongs to a student
        try:
            student_profile = StudentProfile.objects.get(email=email)
            user = student_profile.user
            user_type = 'student'
        except StudentProfile.DoesNotExist:
            # Check if email belongs to a teacher
            try:
                teacher_profile = TeacherProfile.objects.get(user__email=email)
                user = teacher_profile.user
                user_type = 'teacher'
            except TeacherProfile.DoesNotExist:
                messages.error(request, 'No account found with this email.')
                return render(request, 'forgot_password.html')

        # Generate token
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)

        # Save token
        PasswordResetToken.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )

        # Send email
        reset_url = request.build_absolute_uri(f'/reset-password/{token}/')
        subject = 'Password Reset Request - EduAI'
        user_type_display = 'Student' if user_type == 'student' else 'Teacher'
        email_sent_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        message = f'''Hello {user.first_name},

You have requested to reset your password for your EduAI account.

Account Details:
- Name: {user.first_name}
- Username: {user.username}
- Account Type: {user_type_display}

Email sent at: {email_sent_time}

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you did not request this password reset, please ignore this email.

Best regards,
EduAI Support Team
'''
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

        messages.success(request, 'Password reset link sent to your email.')
        return redirect('login')

    return render(request, 'forgot_password.html')

def reset_password(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
        if reset_token.is_expired():
            messages.error(request, 'This reset link has expired.')
            return redirect('login')

        if request.method == 'POST':
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')

            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
            else:
                reset_token.user.set_password(password)
                reset_token.user.save()
                reset_token.delete()  # Remove used token
                messages.success(request, 'Password reset successfully. Please login.')
                return redirect('login')

        return render(request, 'reset_password.html')
    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Invalid reset link.')
        return redirect('login')

@login_required
def img_to_text_ocr(request):
    return render(request, 'img_to_text_ocr.html')



@login_required
def student_semister_content(request):
    # Check if user is a student
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('student_dashboard')

    # Get filter parameters from GET request
    department_filter = request.GET.get('department', student_profile.department)
    semester_filter = request.GET.get('semester', str(student_profile.semester))
    section_filter = request.GET.get('section', '')
    year_filter = request.GET.get('year', str(student_profile.pass_out_year))
    subject_filter = request.GET.get('subject', '')
    content_type_filter = request.GET.get('content_type', '')

    # Filter TeacherSubjectContent based on filters
    contents = TeacherSubjectContent.objects.all()

    if department_filter:
        contents = contents.filter(department=department_filter)
    if semester_filter:
        contents = contents.filter(semester=semester_filter)
    if section_filter:
        contents = contents.filter(section=section_filter)
    if year_filter and year_filter.isdigit():
        contents = contents.filter(year=int(year_filter))
    if subject_filter:
        contents = contents.filter(subject__icontains=subject_filter)
    if content_type_filter:
        contents = contents.filter(content_type=content_type_filter)

    # Get unique values for filter dropdowns
    departments = TeacherSubjectContent.objects.values_list('department', flat=True).distinct()
    semesters = TeacherSubjectContent.objects.values_list('semester', flat=True).distinct()
    sections = TeacherSubjectContent.objects.values_list('section', flat=True).distinct()
    years = TeacherSubjectContent.objects.values_list('year', flat=True).distinct()
    subjects = TeacherSubjectContent.objects.values_list('subject', flat=True).distinct()
    content_types = TeacherSubjectContent.objects.values_list('content_type', flat=True).distinct()

    context = {
        'student_profile': student_profile,
        'contents': contents,
        'department_filter': department_filter,
        'semester_filter': semester_filter,
        'section_filter': section_filter,
        'year_filter': year_filter,
        'subject_filter': subject_filter,
        'content_type_filter': content_type_filter,
        'departments': departments,
        'semesters': semesters,
        'sections': sections,
        'years': years,
        'subjects': subjects,
        'content_types': content_types,
    }
    return render(request, 'student_semister_content.html', context)

@login_required
def available_content_view(request):
    # Show all available content: notes, assignments, quizzes, etc.
    notes = Note.objects.all()
    assignments = Assignment.objects.all()
    quizzes = Quiz.objects.all()
    research_papers = ResearchPaper.objects.all()

    context = {
        'notes': notes,
        'assignments': assignments,
        'quizzes': quizzes,
        'research_papers': research_papers,
    }
    return render(request, 'available_content.html', context)

@login_required
def lock_session(request):
    """
    Lock the document session by clearing PIN verification.
    """
    if 'pin_verified' in request.session:
        del request.session['pin_verified']
    messages.info(request, 'Document session locked. Please verify your PIN to access documents again.')
    return redirect('documents')

@login_required
def semester_progress(request):
    # Check if user is a student
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('student_dashboard')

    # Get semester progress data
    semester = student_profile.semester
    department = student_profile.department
    pass_out_year = student_profile.pass_out_year

    # Calculate progress based on completed courses, quizzes, assignments, etc.
    # This is a placeholder logic - you can improve this based on your models
    total_courses = Course.objects.filter(category__name__icontains=department).count()
    completed_quizzes = QuizAttempt.objects.filter(student=request.user).count()
    submitted_assignments = Submission.objects.filter(student=request.user).count()
    notes_read = Note.objects.filter(course__category__name__icontains=department).count()

    # Simple progress calculation
    progress_percentage = min(100, (completed_quizzes + submitted_assignments + notes_read) * 10)

    # Semester-wise breakdown (placeholder)
    semester_progress_data = []
    for sem in range(1, 9):  # Assuming 8 semesters
        sem_progress = progress_percentage if sem <= semester else 0
        semester_progress_data.append({
            'semester': sem,
            'progress': sem_progress,
            'status': 'Completed' if sem < semester else 'Current' if sem == semester else 'Upcoming'
        })

    context = {
        'student_profile': student_profile,
        'progress_percentage': progress_percentage,
        'semester_progress_data': semester_progress_data,
        'total_courses': total_courses,
        'completed_quizzes': completed_quizzes,
        'submitted_assignments': submitted_assignments,
        'notes_read': notes_read,
    }
    return render(request, 'semester_progress.html', context)

@login_required
def vibhavna_ai(request):
    """
    Render the Vibhavna AI chatbot interface.
    """
    return render(request, 'Vibhavna_AI.html')

@login_required
def settings(request):
    """
    Render the settings page for the user.
    """
    return render(request, 'settings.html')


@login_required
def edit_student_document(request, document_id):
    document = get_object_or_404(StudentDocument, id=document_id, user=request.user)
    if request.method == 'POST':
        form = StudentDocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, 'Document updated successfully!')
            return redirect('documents')
    else:
        form = StudentDocumentForm(instance=document)
    return render(request, 'edit_student_document.html', {'form': form, 'document': document})


@login_required
def delete_student_document(request, document_id):
    document = get_object_or_404(StudentDocument, id=document_id, user=request.user)
    if request.method == 'POST':
        document.delete()
        messages.success(request, 'Document deleted successfully!')
        return redirect('documents')
    return render(request, 'confirm_delete.html', {'object': document, 'type': 'document'})


@login_required
def edit_teacher_document(request, document_id):
    document = get_object_or_404(TeacherDocument, id=document_id, user=request.user)
    if request.method == 'POST':
        form = TeacherDocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, 'Document updated successfully!')
            return redirect('documents')
    else:
        form = TeacherDocumentForm(instance=document)
    return render(request, 'edit_teacher_document.html', {'form': form, 'document': document})


@login_required
def delete_teacher_document(request, document_id):
    document = get_object_or_404(TeacherDocument, id=document_id, user=request.user)
    if request.method == 'POST':
        document.delete()
        messages.success(request, 'Document deleted successfully!')
        return redirect('documents')
    return render(request, 'confirm_delete.html', {'object': document, 'type': 'document'})





