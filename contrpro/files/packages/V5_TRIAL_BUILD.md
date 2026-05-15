# ContractorPro v5 Trial Package - Build Instructions

## Package Structure

### Files to Include in v5 Trial:
1. **Documents (PDF + DOCX):**
   - Preliminary Notice Template (limited fields)
   - Mechanics Lien Form (basic version)
   - README with instructions

2. **Spreadsheets (Excel with protection):**
   - Job Costing Calculator (TRIAL version - limited to 3 projects)
   - Project Tracker (TRIAL version - limited features)
   - INSTRUCTIONS tab in each spreadsheet

3. **SBA Guide:**
   - SBA_Funding_Guide.pdf (excerpt - first 3 chapters only)
   - Or full guide with watermark

4. **Branding:**
   - Footer on all documents: "Powered By Contractor Pros"
   - Links to: LinkedIn, SBA Home Page, ContractorPro.com
   - Trial watermark on all pages

## File Protection Strategy

### Excel Files:
- Lock formula cells (password protected)
- Limit trial to 3 project entries
- Add "TRIAL VERSION" watermark
- Protect structure (no adding sheets)
- Password: ContractorPro2026!

### PDF Files:
- Add watermark: "TRIAL - Purchase Full Version"
- Limit editing capabilities
- Include footer with branding

### Word/DOCX Files:
- Restrict editing to form fields only
- Lock header/footer with branding
- Password protect formatting

## Instructions Integration

### PDF Cover Page:
- Title: "ContractorPro Trial Package - Getting Started"
- Table of contents
- How to use each template
- Upgrade information
- Support contact

### Excel Instructions Tab:
- Sheet name: "START HERE - INSTRUCTIONS"
- Step-by-step guide
- Yellow = fill in, Green = auto-calculate
- Link to purchase full version
- Support email

## Branding Elements

### Footer on All Documents:
```
Powered By Contractor Pros | contractorpro.com
LinkedIn: linkedin.com/company/contractorpro | SBA Resources: sba.gov
© 2026 ContractorPro - Trial Version
```

### Watermark:
- "TRIAL VERSION - Upgrade at contractorpro.com"
- Light gray, diagonal across pages

## Build Commands

```bash
# Create trial package directory
mkdir -p contractorpro-v5-trial/{documents,spreadsheets,sba-guides}

# Copy trial files (limited versions)
cp documents/preliminary-notice-trial.pdf contractorpro-v5-trial/documents/
cp documents/mechanics-lien-trial.docx contractorpro-v5-trial/documents/
cp spreadsheets/job-costing-trial.xlsx contractorpro-v5-trial/spreadsheets/
cp spreadsheets/project-tracker-trial.xlsx contractorpro-v5-trial/spreadsheets/
cp sba-guides/SBA_Guide_Trial.pdf contractorpro-v5-trial/sba-guides/

# Add README with instructions
cp README_v5.txt contractorpro-v5-trial/

# Create zip
zip -r contractorpro-v5-trial.zip contractorpro-v5-trial/
```

## Delivery Configuration Update

Update `delivery-config.js` to include:
- Trial product tier
- File list for trial
- Download restrictions (72 hours, 5 max downloads)
- Upgrade path messaging
