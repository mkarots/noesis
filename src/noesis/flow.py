"""Flow orchestration for sequential agent composition."""

from noesis.core import Agent, AgentResult


class Flow:
    """Sequential agent composition.
    
    Executes agents in order, passing previous output to next agent.
    No DAGs, no parallelism - just simple sequential composition.
    
    Example:
        flow = Flow()
        flow.step("extract", extractor_agent)
        flow.step("analyze", analyzer_agent)
        flow.step("summarize", summarizer_agent)
        
        result = await flow.run({"text": "..."})
    """

    def __init__(self):
        """Initialize empty flow."""
        self.steps: list[tuple[str, Agent]] = []

    def step(self, name: str, agent: Agent) -> "Flow":
        """Add a step to the flow.
        
        Args:
            name: Step name (for debugging/logging)
            agent: Agent to execute at this step
            
        Returns:
            Self for method chaining
        """
        self.steps.append((name, agent))
        return self

    async def run(self, input: dict) -> AgentResult:
        """Execute the flow.
        
        Runs each agent in sequence. If any agent fails, the flow stops
        and returns that failure result.
        
        Each agent receives the previous agent's output in the input
        under the "prev" key, along with the original input.
        
        Args:
            input: Initial input dict
            
        Returns:
            Final AgentResult (or first failure)
        """
        ctx = input
        result = None

        for name, agent in self.steps:
            # Invoke the agent
            result = await agent.invoke(ctx)

            # Stop on failure
            if not result.ok:
                return result

            # Prepare input for next step
            ctx = {"prev": result.output, **input}

        # Return the last result
        return result if result is not None else AgentResult(ok=False, error="Empty flow")

