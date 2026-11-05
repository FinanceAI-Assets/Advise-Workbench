import { EngagementPicker } from "@/components/workbench/EngagementPicker";

export default function ConversationIndexPage() {
  return (
    <EngagementPicker
      area="conversation"
      title="Conversation"
      subtitle="Choose an engagement to continue its conversation. Every thread stays inside its engagement's sources."
    />
  );
}
