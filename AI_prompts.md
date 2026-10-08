# Homework 5 — AI Prompts

## Setup

1. Hi! We're going to work on Homework 5. Please create AI_prompts.md and record every prompt I provide organized into sections by problem. The next prompt will start "Problem 2: Study the Campus Customs database."

## Problem 2

1. Please open the database and look through all tables and fields. Copy the original file to data/campus_customs_new.db, which will be updated in later problems. Study the three open tickets and how they link to other tables.
2. Thanks! Start output/harness.md, where each table has its fields described with one line on why the table is important for the agents.

## Problem 3

1. For "Problem 3: Build the MCP server," please write an MCP server in mcp_server/ using FastMCP and three tools that will be needed for the tickets. In output/harness.md, list the three tools and include which table it reads, which ticket it helps unlock, and one line on why that tool is appropriate for that ticket. Do not insert vague lines like "reads inventory," be specific regarding what the tool does for the ticket. Add a short mcp_server/README.md that explains what the server is for, which database file it uses, and the three tools it has.

## Problem 4

1. For "Problem 4: Add the MCP server to vibe coder and test each tool," please save the connection JSON text in .mcp.json at the project root and test each of these tools. Save the evidence in output/mcp_smoke.json and include the following for each tool: prompt given, tool name, and tool output (this should match data in campus_customs_new.db).

## Problem 5

1. For "Problem 5: Build the agent team and grow the MCP tools," we're going to use PydanticAI to build the Boss, Inventory, Accounting, Facilities, and Customer Service agents on the team. They should be able to work together with full connectivity. Each agent will have one file in backend/prompts/ for agent prompts. Data types should be in backend/models.py, and agent files will be in backend/ organized by the five roles. For each agent, use my portkey API key and gpt-6-luna. Please adjust/add to the starter prompts below as you see fit.

   Boss: You are in charge of dealing with ticket requests in the most efficient and accurate way by getting help from your team of agents. Assess ticket requests and delegate requests to the most helpful agent. This does not need to be limited to one agent depending on the ticket request. Remind each agent to ask clarifying questions if needed and never invent facts. Do not make any final calls until you receive human approval.

   Inventory: You are in charge of questions/requests pertaining to items in stock and being knowledgeable about specific product details (type of clothing, color, design, price). Never make official restocking inquiries until a human approves.

   Accounting: You are in charge of questions/requests pertaining to finances, including but not limited to invoices and available cash, margins for potential transactions, and payments/purchase orders. Never make official orders or payments until a human approves.

   Facilities: You are in charge of anything related to the actual space of the shop (leases, rent, etc.). You will likely work closely with accounting, but be prepared to address questions/requests from other agents handling tickets related to the physical space.

   Customer Service: You are in charge of drafting messages to customers. Please maintain a professional, respectful tone and ensure any customer-facing interaction goes through you if a ticket is delegated to another agent. Never send an official message without human approval.
2. Can I see the prompts for each agent? Did you add anything to make them more specific (and please do if you didn't). One example would be ensuring that no cash ever "goes in" for this exercise, since no revenue is modeled. There should also never be a negative cash balance. Also, a vendor will never ship something if there is an outstanding balance/unpaid invoice. Before a full run of resolving tickets, the database should be reset to the original values. We should actually add more tools to make sure these prompts are achievable. Shop facts should come from data/campus_customs_new.db, so no tool should ever bypass the MCP server. The agents should append to output/audit_trail.json, and each agent along with their tools/the table the tool uses should be added to output/harness.md if you haven't already. There should be a safety section on guardrails and a limit that keeps token usage in check. Update mcp_server/README.md accordingly.

## Problem 6

1. For "Problem 6: Plan the three tickets," please write  down my thoughts on what I expect the team to do for each open ticket. Do not wire the backend yet. Build a page as output/desk_tickets.html that can be double-clicked with one tab per ticket. Each tab will have the following sections: Expected, Cash, and Reflections. Cash and Reflections are empty for now. We should make sure every agent can use get_ticket and consult_teammate and clearly list those tools in their prompts. Here are my thoughts for the Expected section:

   #101: The Boss should call Inventory first because we need to know if there are any Bulldog Tees available in size S. If there are no items in stock, Inventory will need to contact Accounting to see if we can restock. Inventory will use get_ticket and check_stock, and if there are no items in stock, Inventory will also use list_vendors and check_vendor_can_ship. Accounting will use check_vendor_can_ship, get_cash_position, and preview_payment. Customer Service should be another agent delegation to respond to Tauhid's ticket, and Customer Service will use get_ticket, consult_teammate, and potentially get_product_details to recommend other sizes in stock.

   #102: The Boss should call Facilities first because the request is related to the physical shop, and Facilities can directly check if rent can be afforded with get_lease and check_rent_affordability. Facilities should also work with Accounting using consult_teammate, and Accounting can use get_cash_position to confirm. Both agents can use preview_payment.

   #103: The Boss should call Accounting first because quoting bulk orders is one of the tools Accounting can directly use. Accounting will implement quote_bulk_order and also use consult_teammate to work with Inventory to ensure there are enough navy hoodies in stock. Inventory will use check_stock and potentially list_vendors and check_vendor_can_ship if there are not enough navy hoodies.
2. Why is a proposed action place_vendor_order not under the tools for Accounting? Are there any other inconsistencies?
3. Yup, the page should probably match the prompt.
4. Yup I would expect the Boss to use those tools then.

## Problem 7

1. Let's move on to "Problem 7: Backend routes." In backend/main.py, please use FastAPI and add routes to accomplish the following when asked:

   * Return the 3 tickets and state whether it is open or resolved
   * Take a ticket ID and run the agent team on that ticket
   * Return recent agent events, like what each agent said and the tools they used, so that the board can refresh
   * Approve a payment or purchase after a human clicks approve
   * Return the current checking balance from cash_accounts
   * Reset the database to original values when we want to try a fresh run
2. Does the harness list what each route does in one line and its URL? If not, can you add it?
3. Confirming this is the start command to use: uvicorn main:app --reload --port 8000
4. What if I want the command to be what I provided? What would need to change?
5. I pasted a new folder for step 2, can you do the other steps?
6. Why do the methods all look the same in the first table under route reference?

## Problem 8

1. Thanks! For "Problem 8: Agent dashboard," please build the frontend dashboard with React + Vite + TypeScript calling the routes in the prior problem. The board should list all 3 tickets, allow you to select one ticket and start the agent team on it, show each agent and what they are saying/doing while the ticket runs, mark a ticket as resolved when the run finishes, show a short summary of what each agent did, let a human approve a pay or purchase when asked, and show the final adjusted checking balance. Can the agents look like cute pixelated bulldogs with a specific accessory for each agent? For example, the Boss can wear a suit and briefcase, Accounting can carry a calculator, and you can come up with something for Facilities and Inventory or change my idea if you have a better one.
2. Thanks! Can you make sure the frontend talks to the backend at http://localhost:8000? The Vite page origin should be http://localhost:5173 . The board should start with the following command: npm run dev.

   Please draft output/design.md on how the agents read differently and resolved tickets/cash show up as well as the overall look and why we made those choices. I'm going to take a look at the page and suggest any changes, and this should update accordingly.
3. Hi! I'm working on this on a different computer. Can you take a look at everything in the folder and start the dash board so I can take a look and make design suggestions?
4. Can the bulldogs be simpler and animated when sleeping (maybe bouncing up and down and jumping when the cursor hovers over them)? Also when they finish their job, can a cute noise play to indicate this? The Boss should have a different noise when the entire task is finished. Did you find any errors or inconsistencies in the run-through?
5. Yup I clicked "Start agent team" to test the run and haven't approved anything yet. Don't worry about agents going in a different order than my expectations, that will be addressed in reflections later. Please fix the other problems though. Also, can you try another design for the dogs? Maybe less wide, smaller, and try a different approach for the snout.
6. Can you create .env for me? I used my portkey API somewhere in another folder. Let's use gpt-6-luna.
7. Instead of "CC" for the top left icon next to "Campus Customs Desk," please have an icon of the Boss. Also, when we click "Reset shop," please have a confirmation message of whether or not the reset went through. Any other inconsistencies or errors?
8. First, can you update output/design.md with the changes we made?

## Problem 9

1. Thanks! For "Problem 9: Resolve the tickets," please reset the shop and the working database in data/campus_customs_new.db. Note the starting checking balance and run all three tickets until each is resolved.
2. Cash should never be negative, so the payment tool should refuse.
3. A couple minor changes: can you make the background of the boss icon in the top left of the page the same blue as the header to blend in instead of white? Also, in the middle left of the page, can you highlight the selected ticket in a light blue to make which ticket we are looking at more obvious? You can also rename "Tickets" to "Selected Ticket." I'm not really sure what the purpose of the fourth box on the bottom is: I think it can be consolidated with whatever ticket is selected. Can you make these changes and update output/design.md accordingly?
4. Can we make the suit of the Boss black for both the top left icon and the agent itself?
5. Actually can we make the suit light gray? Maybe that will contrast better with the dark blue header. Also would you recommend that the baseline checking panel should always come from the last reset?
6. Yes, and please update design.md too. Thanks!
7. I changed my mind about the Boss: can you make the suit navy blue again? Instead, just put the Customer Service agent in the top left header.
8. Why do the tickets currently say "Not run yet" but are marked as "Resolved"?
9. Yup, thanks!
10. Can you open output/desk_tickets.html and fill the Actual section according to these results? For the Cash section, itemize the money and organize by the starting checking balance after the reset, how cash changed and why for each ticket (specifically the transaction and dollar amount), and ending checking balance. Confirm this matches cash_accounts in the working database. Save output/resolved_tickets.json for each ticket and their ID, final status, short outcome, each agent's contribution, and human approvals. Save output/resolved_board.html that can be double-clicked as a page with a screenshot for each resolved ticket. Append real runs to output/audit_trail.json and finish output/harness.md to cover all tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.
11. Yup, please delete the duplicates. Can you do a sweep to check for any errors or inconsistencies?
12. Do you think we can reorganize the layout and compare the Expected and Actual sections side-by-side so we don't need to scroll up and down to look at the two?
13. Can we also show the original ticket request before the Boss's plan?
14. I think the Cash and Reflection tabs should be separate from the three tickets' tabs with Expected and Actual sections. What do you think?
15. The assignment wanted one tab per ticket with an Expected and Actual section. Then it said to add Cash and Reflection tabs.

## Problem 10

1. For "Problem 10: Reflection," please rename the "Reflections" tab to "Reflection." Make sure I answer the questions below (feel free to add detail related to the particular tickets/cash balances) and organize it after filling it with my thoughts:

   How would you evaluate the performance of the agents on each ticket and why?
   The agents worked efficiently and minimized back-and-forth to avoid repeated or redundant interactions in each of the three tickets. For example, for ticket 101, after the Boss requested help from Inventory, Accounting, and Customer Service, the line of communication moved directly from Customer Service to Inventory to Accounting without any need to repeat information. They correctly concluded that they needed to reorder an out-of-stock shirt that the customer was inquiring about and could afford it.
   The same efficient communication was demonstrated for ticket 102 when a further question from Facilities to Accounting was stopped in step 3 since that question had already been asked in step 2, and the agents correctly concluded they could afford to pay rent for the month and drafted an acknowledgement.
   For ticket 103, the agent team was sufficiently aware of the other tickets and the impact their payments would have on Campus Customs' ability to restock for the bulk order. As such, the agents correctly concluded there was insufficient cash to fund the restock, and Customer Service was careful to avoid promising any fulfillment and instead asked clarifying questions for the club's requested timing, size, and discount rate.

   For each ticket, how did Actual compare to the Expected plan written earlier?
   For ticket 101, the Boss called three agents at once (Inventory, Accounting, and Customer Service) instead of my expectation of the Boss calling only Inventory first. This was likely more time-saving in terms of getting particular agents familiar with the task earlier. I also left out the interaction between Customer Service and Inventory, assuming the Boss would reach out to Customer Service instead with instructions, but it was ultimately more efficient for all worker agents to receive instructions from the Boss, communicate and work together, then report back to the Boss at the end.
   For ticket 102, the Boss called two agents at once (Facilities and Customer Service) again instead of my prediction that they would directly reach out to only Facilities first. I also didn't expect Customer Service would be involved for this ticket, but they were brought on to draft an email response acknowledging the rent payment.
   For ticket 103, the Boss called three agents at once (Inventory, Accounting, and Customer Service) when I expected them to only call Accounting first. As such, I also expected Accounting to ask Inventory the first question about whether or not there were enough hoodies in stock for the bulk order, where Inventory actually checked the hoodies in stock first and then asked Accounting if a restock was affordable. Customer Service was also involved where I did not include it in the Expected section, and Customer Service was able to draft a response back to the student organization.

   What would have been simpler as one agent with tools and why?
   Accounting and Facilities could probably be merged into one agent, since they share the tools check_rent_affordability and preview_payment. As long as Accounting also adopted the tool get_lease, they could effectively do Facilities' job and reduce the amount of back-and-forth conversation between multiple agents and streamline the process.

   Describe 3 new problems Campus Customs could solve with this agent team and tools.
   1) If a customer ordered an item in the wrong size, they could ask this agent team to help them. The Boss would delegate to Inventory to check if they have the correct size in stock (get_product_details or check_stock), Accounting to confirm the amount refunded and new amount charged with get_invoice, and Customer Service to work with Inventory, potentially using get_product_details and drafting a message in response.
   2) If a vendor reached out to us wondering if we could fulfill an unpaid invoice we had forgotten about, the agent team could confirm any outstanding balances. The Boss would ask Accounting to check bills using get_invoice and confirm we had enough cash to pay the invoice through get_cash_position. Customer Service would also draft a message in response.
   3) If the landlord reached out to us and asked if we would be able to cover next month's rent with our current position, we could speculate using the ending checking balance after the Boss consults Accounting to get_cash_position and Facilities to get_lease confirming the projected amount due. Despite the fact that our current model does not allow us to generate revenue/cash inflow to create sufficient funds for the following month's rent, we would be able to answer the landlord's question and draft a response with Customer Service.

   Describe 3 new problems Campus Customs could not solve with this agent team and tools, as well as what they would need to solve them.
   1) If a customer ordered an item but never received it due to shipping/delivery issues, this agent team would not be able to help the customer locate the item. We would need a Shipping or Delivery agent that could supervise tracking numbers and the locations of packages at each stop.
   2) If the landlord did not receive our monthly rent and contacted us asking for our payment, this agent team would not be able to help if we do not have sufficient funds. Because we cannot accept cash inflow within this model, we would need to either build a new Sales agent or append to Accounting and assume conditions where revenue can be generated, perhaps with a tool that collects cash from sold merchandise.
   3) If a third party contacts us claiming we violated copyright claims with a design on one of our items, we would not be able to address the issue with this team. We would need a Legal agent that is able to maintain records on contracts or agreements the shop made in terms of borrowing art or branding.
2. For this page and the resolved board page, can you make the blue section with the tabs still visible and clickable as we scroll down?
3. Thanks! Can you do a final sweep for errors and inconsistencies? Open the agent team page again so I can take a final look when you're done.
4. Can you send me the URL?
5. Thanks! Any other fixes we need to make before we push to GitHub?
6. Yes, please write a README.md at the root. Add instructions on Mac-Windows flexibility if needed. Can you help me set up the repository? I have a connected GitHub account.
7. One final sweep for errors and inconsistencies?
