"""批量评测 5 个真实开源项目，验证五维 Rubric 区分度。"""
import os
import sys

os.environ["GITHUB_VERIFY_SSL"] = "false"
sys.path.insert(0, r"D:\codebase\作品集\竞品雷达")

from dotenv import load_dotenv

load_dotenv()

from modules.evaluator import collect_repo, evaluate_product, search_competitors

PROJECTS = [
    ("https://github.com/pallets/flask", "Python web micro-framework"),
    ("https://github.com/vuejs/petite-vue", "Lightweight Vue subset (archived)"),
    ("https://github.com/mitmproxy/pdoc", "Auto-generated API docs for Python"),
    ("https://github.com/tiangolo/typer", "CLI framework built on Click"),
    ("https://github.com/nicedoc/nicedoc", "Documentation generator"),
    ("https://github.com/mckinsey/vizro", "Low-code dashboard framework"),
    ("https://github.com/casey/just", "Command runner (like make)"),
]

results = []
for url, desc in PROJECTS:
    print(f"\n{'='*60}")
    print(f"Evaluating: {url}")
    print(f"{'='*60}")

    try:
        project = collect_repo(url)
        if project.error:
            print(f"  SKIP: {project.error}")
            continue

        print(f"  Collected: {project.full_name} | Stars:{project.stars} | Commits:{project.commit_days_active_90d}d")

        competitors = search_competitors(desc or project.description, n=3, use_llm=False)
        print(f"  Competitors: {[c.full_name for c in competitors]}")

        eval_result = evaluate_product(project, competitors)
        wt = eval_result["weighted_total"]
        summary = eval_result["overall_summary"]
        print(f"  SCORE: {wt:.2f}/2.00")
        if "_calibrations" in eval_result:
            for cal in eval_result["_calibrations"]:
                print(f"    [CALIB] {cal}")
        print(f"  Summary: {summary}")
        for k, v in eval_result["scores"].items():
            print(f"    {v['name']}: {v['score']}/2")
        print(f"  Strengths: {eval_result['top_strengths']}")
        print(f"  Weaknesses: {eval_result['top_weaknesses']}")

        results.append({
            "repo": project.full_name,
            "stars": project.stars,
            "score": wt,
            "positioning": eval_result["scores"]["positioning"]["score"],
            "differentiation": eval_result["scores"]["differentiation"]["score"],
            "moat": eval_result["scores"]["moat"]["score"],
            "engineering": eval_result["scores"]["engineering"]["score"],
            "sustainability": eval_result["scores"]["sustainability"]["score"],
        })

    except Exception as e:
        print(f"  FAILED: {e}")

print(f"\n{'='*60}")
print("FINAL RESULTS - Ranking by score:")
print(f"{'='*60}")
results.sort(key=lambda r: r["score"], reverse=True)
print(f"{'Repo':<30} {'Stars':>8} {'Score':>6} P D M E S")
print("-" * 60)
for r in results:
    print(f"{r['repo']:<30} {r['stars']:>8,} {r['score']:>5.2f}  {r['positioning']} {r['differentiation']} {r['moat']} {r['engineering']} {r['sustainability']}")

scores = [r["score"] for r in results]
if len(scores) >= 2:
    print(f"\nScore range: {min(scores):.2f} - {max(scores):.2f} (spread: {max(scores)-min(scores):.2f})")
    print(f"Mean: {sum(scores)/len(scores):.2f}")
