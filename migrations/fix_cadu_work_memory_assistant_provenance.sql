-- Proposals extracted from assistant turns must not name the user as source author.
UPDATE cadu_working_memories memory
   SET source_author_id = NULL
 WHERE memory.source_author_id IS NOT NULL
   AND EXISTS (
       SELECT 1 FROM cadu_conversation_messages message
        WHERE message.id = memory.source_message_id::text
          AND message.conversation_id = memory.source_conversation_id
          AND message.role = 'assistant'
   );

UPDATE cadu_working_memory_events event
   SET actor_id = NULL,
       detail = jsonb_set(event.detail, '{source}', '"assistant_answer"'::jsonb, true)
  FROM cadu_working_memories memory
 WHERE event.memory_id = memory.id
   AND event.event = 'proposed'
   AND event.detail->>'source' = 'conversation'
   AND EXISTS (
       SELECT 1 FROM cadu_conversation_messages message
        WHERE message.id = memory.source_message_id::text
          AND message.conversation_id = memory.source_conversation_id
          AND message.role = 'assistant'
   );
