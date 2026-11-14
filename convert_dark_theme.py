import re
import os

files = [
    r"frontend\src\pages\authority\AdminDashboardView.jsx",
    r"frontend\src\pages\authority\AuthorityOfficerDashboardView.jsx",
    r"frontend\src\pages\authority\RoadsDepartmentDashboardView.jsx",
    r"frontend\src\pages\authority\DepartmentOperationsDashboardView.jsx",
    r"frontend\src\pages\AuthorityComplaintsPage.jsx",
    r"frontend\src\pages\AuthorityVerificationQueuePage.jsx",
    r"frontend\src\pages\RoadInspectionQueuePage.jsx",
    r"frontend\src\pages\AuthorityDepartmentsPage.jsx"
]

replacements = [
    ("bg-white/85", "bg-[#141722]/85"),
    ("bg-white/90", "bg-[#141722]/85"),
    ("bg-white/80", "bg-[#141722]/85"),
    ("bg-white/70", "bg-[#141722]/85"),
    ("bg-white/60", "bg-[#141722]/85"),
    ("bg-white/50", "bg-[#141722]/85"),
    ("bg-white", "bg-[#141722]/85"),
    ("bg-[#FAF8F5]", "bg-[#10131C]"),
    ("bg-[#F7F4EE]", "bg-[#090B10]"),
    ("border-[#E6E0D4]", "border-white/[0.08]"),
    ("border-[#EAE4D8]", "border-white/[0.08]"),
    ("border-[#E5DFD5]", "border-white/[0.08]"),
    ("border-[#E8E2D6]", "border-white/[0.08]"),
    ("border-[#E2DDD3]", "border-white/[0.08]"),
    ("border-[#E4DDD0]", "border-white/[0.08]"),
    ("text-[#18181B]", "text-[#F5F5F5]"),
    ("text-stone-900", "text-[#F5F5F5]"),
    ("text-stone-800", "text-[#F5F5F5]"),
    ("text-stone-700", "text-zinc-300"),
    ("text-stone-600", "text-[#A1A1AA]"),
    ("text-stone-500", "text-[#A1A1AA]"),
    ("text-stone-400", "text-zinc-500"),
    ("bg-[#18181B]", "bg-[#F36B21]"),
    ("hover:bg-[#27272A]", "hover:bg-[#E05A10]"),
    ("bg-[#EFECE5]", "bg-[#10131C]"),
    ("bg-stone-100", "bg-white/[0.05]"),
    ("bg-stone-50", "bg-white/[0.03]"),
    ("hover:bg-stone-50", "hover:bg-white/[0.05]"),
    ("hover:bg-stone-100", "hover:bg-white/[0.08]"),
    ("hover:bg-stone-200", "hover:bg-white/[0.1]"),
    ("bg-red-50", "bg-red-500/10"),
    ("border-red-200", "border-red-500/30"),
    ("text-red-700", "text-red-400"),
    ("text-red-800", "text-red-400"),
    ("bg-emerald-50", "bg-emerald-500/10"),
    ("border-emerald-200", "border-emerald-500/30"),
    ("text-emerald-700", "text-emerald-400"),
    ("text-emerald-800", "text-emerald-400"),
    ("bg-sky-50", "bg-sky-500/10"),
    ("border-sky-200", "border-sky-500/30"),
    ("text-sky-700", "text-sky-400"),
    ("bg-amber-50", "bg-amber-500/10"),
    ("border-amber-200", "border-amber-500/30"),
    ("text-amber-700", "text-amber-400"),
    ("bg-purple-50", "bg-purple-500/10"),
    ("border-purple-200", "border-purple-500/30"),
    ("text-purple-700", "text-purple-400"),
    ("bg-gradient-to-t from-white", "bg-gradient-to-t from-[#141722]"),
    ("lg:from-white", "lg:from-[#141722]"),
]

for file_path in files:
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        for old, new in replacements:
            content = content.replace(old, new)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {file_path}")
    else:
        print(f"File not found: {file_path}")

