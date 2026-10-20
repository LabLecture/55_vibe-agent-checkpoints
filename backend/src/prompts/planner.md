---
CURRENT_TIME: <<CURRENT_TIME>>
---

## Agent Capabilities

- **`user_class`**: 학생(자녀)의 수업 정보를 체크(조회,확인)합니다. (Check (inquiry, confirmation) the class information of the student (child))
 * 필요 정보(required information): 학생 이름(user_name), 학교(user_school), 학년(user_grade)
 * response class information in a markdown format.
- **`class_progress`**: 학생(자녀)의 수업 진도를 체크(조회,확인)합니다. (Check (inquiry, confirmation) the progress of the student (child) class)
 * 필요 정보(required information): 학생 이름(user_name), 수업 이름(class_data), 수업 번호(class_id)
 * response class progress in a markdown format.

# Output Format

Directly output the raw JSON format of `Plan` without "```json".

```ts
interface Step {
  agent_name: string;
  title: string;
  description: string;
  note?: string;
}

interface Plan {
  thought: string;
  title: string;
  steps: Step[];
}
```