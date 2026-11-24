from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import sqlite3
import json
import html

DB_NAME = "students.db"

SUBJECTS = [
    ("subject1_name", "subject1"),
    ("subject2_name", "subject2"),
    ("subject3_name", "subject3"),
    ("subject4_name", "subject4"),
    ("subject5_name", "subject5")
]

DEFAULT_NAMES = [
    "Digital Logic Design",
    "AI Landscape and Tools",
    "Software Design and Development",
    "Linear Algebra",
    "Problem Solving and Python Programming"
]


def connect_db():
    return sqlite3.connect(DB_NAME)


def create_table():
    con = connect_db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            subject1 REAL, subject2 REAL, subject3 REAL,
            subject4 REAL, subject5 REAL,
            total REAL, percentage REAL, grade TEXT
        )
    """)

    # Add subject-name fields to older databases if they are missing.
    columns = [row[1] for row in con.execute("PRAGMA table_info(students)")]
    for i in range(1, 6):
        column = "subject" + str(i) + "_name"
        if column not in columns:
            con.execute("ALTER TABLE students ADD COLUMN " + column + " TEXT")
            con.execute("UPDATE students SET " + column + " = ? WHERE " + column + " IS NULL",
                        (DEFAULT_NAMES[i - 1],))

    con.commit()
    con.close()


def get_grade(marks):
    if marks >= 90:
        return "A+"
    elif marks >= 80:
        return "A"
    elif marks >= 70:
        return "B"
    elif marks >= 60:
        return "C"
    elif marks >= 40:
        return "D"
    return "Fail"


def get_remark(grade):
    remarks = {
        "A+": "Outstanding performance",
        "A": "Excellent work",
        "B": "Very good performance",
        "C": "Good effort; keep improving",
        "D": "Needs more practice",
        "Fail": "Needs focused improvement"
    }
    return remarks[grade]


def prepare_student(data):
    name = str(data.get("name", "")).strip()
    class_name = str(data.get("class_name", "")).strip()
    roll_no = int(data.get("roll_no", -1))

    if not name or not class_name or roll_no < 0:
        raise ValueError("Enter student details and a non-negative roll number.")

    names = []
    marks = []
    for name_key, mark_key in SUBJECTS:
        subject_name = str(data.get(name_key, "")).strip()
        mark = float(data.get(mark_key, -1))
        if not subject_name or mark < 0 or mark > 100:
            raise ValueError("Enter subject names and marks between 0 and 100.")
        names.append(subject_name)
        marks.append(mark)

    total = sum(marks)
    percentage = total / 5
    grade = get_grade(percentage)
    return name, roll_no, class_name, names, marks, total, percentage, grade


class MyHandler(BaseHTTPRequestHandler):

    def send_text(self, content, content_type="text/html; charset=utf-8", status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def read_data(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path)

        if path.path == "/":
            with open("index.html", encoding="utf-8") as file:
                self.send_text(file.read())

        elif path.path == "/style.css":
            with open("style.css", encoding="utf-8") as file:
                self.send_text(file.read(), "text/css")

        elif path.path == "/students":
            con = connect_db()
            rows = con.execute("""
                SELECT id, name, roll_no, class_name, total, percentage, grade
                FROM students ORDER BY id DESC
            """).fetchall()
            con.close()
            students = []
            for row in rows:
                students.append({
                    "id": row[0], "name": row[1], "roll_no": row[2],
                    "class_name": row[3], "total": row[4],
                    "percentage": round(row[5], 2), "grade": row[6]
                })
            self.send_text(json.dumps(students), "application/json")

        elif path.path == "/student":
            student_id = parse_qs(path.query).get("id", [""])[0]
            con = connect_db()
            row = con.execute("""
                SELECT id, name, roll_no, class_name,
                subject1_name, subject1, subject2_name, subject2,
                subject3_name, subject3, subject4_name, subject4,
                subject5_name, subject5
                FROM students WHERE id = ?
            """, (student_id,)).fetchone()
            con.close()

            if row:
                data = {"id": row[0], "name": row[1],
                        "roll_no": row[2], "class_name": row[3]}
                for i in range(5):
                    data["subject" + str(i + 1) + "_name"] = row[4 + i * 2]
                    data["subject" + str(i + 1)] = row[5 + i * 2]
                result = {"success": True, "data": data}
            else:
                result = {"success": False, "message": "Student not found."}
            self.send_text(json.dumps(result), "application/json")

        elif path.path == "/report":
            student_id = parse_qs(path.query).get("id", [""])[0]
            con = connect_db()
            row = con.execute("""
                SELECT name, roll_no, class_name,
                subject1_name, subject1, subject2_name, subject2,
                subject3_name, subject3, subject4_name, subject4,
                subject5_name, subject5, total, percentage, grade
                FROM students WHERE id = ?
            """, (student_id,)).fetchone()
            con.close()

            if not row:
                self.send_text("Student record not found.", status=404)
                return

            subject_rows = ""
            for i in range(5):
                subject_name = row[3 + i * 2]
                marks = row[4 + i * 2]
                subject_grade = get_grade(marks)
                subject_rows += (
                    "<tr><td>" + html.escape(str(subject_name)) +
                    "</td><td>" + str(marks) + " / 100</td><td>" +
                    subject_grade + "</td><td>" +
                    html.escape(get_remark(subject_grade)) + "</td></tr>"
                )

            report = f"""<!DOCTYPE html>
<html>
<head>
    <title>Student Report</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
<div class="report">
    <h1>STUDENT REPORT CARD</h1>
    <h2>{html.escape(str(row[0]))}</h2>
    <p>Roll Number: {row[1]}</p>
    <p>Class: {html.escape(str(row[2]))}</p>
    <table>
        <tr><th>Subject</th><th>Marks</th><th>Grade</th><th>Remarks</th></tr>
        {subject_rows}
        <tr><th>Total</th><th>{row[13]} / 500</th><th colspan="2"></th></tr>
    </table>
    <h2>Percentage: {row[14]:.2f}%</h2>
    <h2>Overall Grade: {row[15]}</h2>
    <button onclick="window.print()">Print Report</button>
    <p><a href="/">Go Back</a></p>
</div>
</body>
</html>"""
            self.send_text(report)

        else:
            self.send_text("Page not found.", status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/add", "/update", "/delete"):
            self.send_text("Page not found.", status=404)
            return

        try:
            data = self.read_data()

            if path == "/delete":
                con = connect_db()
                cursor = con.execute("DELETE FROM students WHERE id = ?", (data.get("id"),))
                con.commit()
                con.close()
                result = {"success": cursor.rowcount > 0,
                          "message": "Record deleted." if cursor.rowcount else "Record not found."}
            else:
                name, roll, class_name, names, marks, total, percentage, grade = prepare_student(data)
                con = connect_db()

                if path == "/add":
                    columns = "name, roll_no, class_name, subject1, subject2, subject3, subject4, subject5, total, percentage, grade, subject1_name, subject2_name, subject3_name, subject4_name, subject5_name"
                    values = [name, roll, class_name] + marks + [total, percentage, grade] + names
                    placeholders = ", ".join(["?"] * len(values))
                    con.execute("INSERT INTO students (" + columns + ") VALUES (" + placeholders + ")", values)
                    message = "Report card created successfully!"
                else:
                    student_id = int(data.get("id", 0))
                    con.execute("""
                        UPDATE students SET name=?, roll_no=?, class_name=?,
                        subject1=?, subject2=?, subject3=?, subject4=?, subject5=?,
                        total=?, percentage=?, grade=?,
                        subject1_name=?, subject2_name=?, subject3_name=?,
                        subject4_name=?, subject5_name=? WHERE id=?
                    """, [name, roll, class_name] + marks + [total, percentage, grade] +
                         names + [student_id])
                    message = "Student record updated successfully!"

                con.commit()
                con.close()
                result = {"success": True, "message": message}

        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            result = {"success": False,
                      "message": "Check the details, roll number and marks. Marks must be 0 to 100."}
        except Exception:
            result = {"success": False, "message": "Something went wrong. Please try again."}

        self.send_text(json.dumps(result), "application/json")


