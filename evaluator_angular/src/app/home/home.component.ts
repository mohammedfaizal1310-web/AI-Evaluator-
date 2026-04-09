import { Component } from '@angular/core';
import { ServiceService } from '../Services/service.service';
import { finalize, forkJoin, switchMap } from 'rxjs';
import { CommonModule } from '@angular/common';
import { NgxSpinnerModule, NgxSpinnerService } from 'ngx-spinner';
import { ToastrService } from 'ngx-toastr';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, NgxSpinnerModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss'
})
export class HomeComponent {
  rfpFiles: File[] = [];
  proposalFiles: File[] = [];
  evaluationResults: any[] = [];

  // For showing file names after refresh
  savedRfpName: string | null = null;
  savedProposalNames: string[] = [];

  // Static headers always present


  // Will be dynamically filled based on API result
  dynamicHeaders: string[] = [];

  private readonly RFP_KEY = 'rfpFileNames';
  private readonly PROPOSAL_KEY = 'proposalFileNames';

  constructor(
    private ncgrService: ServiceService,
    private spinner: NgxSpinnerService,
    private toastr: ToastrService
  ) { }

  ngOnInit() {
    // ✅ Restore results/headers
    const savedResults = localStorage.getItem('evaluationResults');
    if (savedResults) this.evaluationResults = JSON.parse(savedResults);

    const savedHeaders = localStorage.getItem('dynamicHeaders');
    if (savedHeaders) this.dynamicHeaders = JSON.parse(savedHeaders);

    // ✅ Restore file names (for UI display only)
    const savedRfp = localStorage.getItem(this.RFP_KEY);
    if (savedRfp) this.savedRfpName = JSON.parse(savedRfp);

    const savedProposals = localStorage.getItem(this.PROPOSAL_KEY);
    if (savedProposals) this.savedProposalNames = JSON.parse(savedProposals);
  }

  // Combined table headers
  get tableHeaders(): string[] {
    return this.dynamicHeaders;
  }

  private norm(name: string) {
    return name.normalize('NFC').trim();
  }

  onFileSelect(event: any, type: 'rfp' | 'proposals') {
    const input = event.target as HTMLInputElement;
    const files: FileList | null = input.files;
    if (!files || !files.length) return;

    for (const file of Array.from(files)) {
      if (!this.isValidFileType(file)) {
        alert(`Invalid format: ${file.name}. Please upload only TEXT files (.txt)`);
        continue;
      }

      if (type === 'rfp') {
        this.rfpFiles = [file]; // only 1 RFP
        this.savedRfpName = file.name;
      } else {
        const nameN = this.norm(file.name);
        const idx = this.proposalFiles.findIndex(f => this.norm(f.name) === nameN);
        if (idx > -1) {
          this.proposalFiles[idx] = file; // replace
        } else {
          this.proposalFiles.push(file);
        }
        if (!this.savedProposalNames.includes(file.name)) {
          this.savedProposalNames.push(file.name);
        }
      }
    }

    // ✅ Save just file names
    this.persistFileNames();

    input.value = '';
  }

  isValidFileType(file: File): boolean {
    return file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt');
  }

  removeFile(file: File | string, type: 'rfp' | 'proposals') {
    if (type === 'rfp') {
      this.rfpFiles = [];
      this.savedRfpName = null;
    } else {
      const fileName = typeof file === 'string' ? file : file.name;
      this.proposalFiles = this.proposalFiles.filter(f => this.norm(f.name) !== this.norm(fileName));
      this.savedProposalNames = this.savedProposalNames.filter(n => this.norm(n) !== this.norm(fileName));
    }

    // ✅ Update storage
    this.persistFileNames();
  }

  get canEvaluate(): boolean {
    // Must have at least 1 real RFP and 1 Proposal file
    return this.rfpFiles.length > 0 && this.proposalFiles.length > 0;
  }

  disableFieldsOnEvaluate = false;
  evaluate() {

    this.disableFieldsOnEvaluate = true;
    if (this.rfpFiles.length === 0 || this.proposalFiles.length === 0) {
      alert('Please upload both RFP and at least one Proposal document.');
      return;
    }

    const formData = new FormData();
    formData.append('rfp', this.rfpFiles[0], this.rfpFiles[0].name);
    this.proposalFiles.forEach(f => formData.append('proposals', f, f.name));

    // this.spinner.show();

    this.ncgrService.clearDocs().pipe(
      switchMap(() => this.ncgrService.uploadFiles(formData)),
      switchMap(() => this.ncgrService.evaluateDocs(formData)),
      finalize(() => this.spinner.hide())
    ).subscribe({
      next: (evalRes) => {
        
        
        this.toastr.success('Evaluation completed successfully', 'Success', { positionClass: 'toast-top-right' });
        this.disableFieldsOnEvaluate = false;

        this.evaluationResults = evalRes?.evaluation_table || [];
        console.log("test",this.evaluationResults);
        localStorage.setItem('evaluationResults', JSON.stringify(this.evaluationResults));

        if (this.evaluationResults.length) {
          const firstRow = this.evaluationResults[0];
          const rawHeaders = Object.keys(firstRow)

          

          const prefixes = Array.from(new Set(rawHeaders.map(h => h.split(' ')[0])));
          
          this.dynamicHeaders = [];

          rawHeaders.forEach(prefix => {
            this.dynamicHeaders.push(prefix)
            // const scoreKey = rawHeaders.find(h => h.toLowerCase().includes('score') && h.startsWith(prefix));
            // if (scoreKey) this.dynamicHeaders.push(scoreKey);

            // const reasonKey = rawHeaders.find(h => h.toLowerCase().includes('reason') && h.startsWith(prefix));
            // if (reasonKey) this.dynamicHeaders.push(reasonKey);

            // const refKey = rawHeaders.find(h => h.toLowerCase().includes('reference') && h.startsWith(prefix));
            // if (refKey) this.dynamicHeaders.push(refKey);
          });

          
          console.log("test",this.dynamicHeaders);

          localStorage.setItem('dynamicHeaders', JSON.stringify(this.dynamicHeaders));
        }
      },
      error: (err) => {
        console.error('Evaluation Error:', err);
        this.toastr.error('Evaluation failed', 'Error', { positionClass: 'toast-top-right' });
        this.disableFieldsOnEvaluate = false;
      }
    });
  }

  clearDocs() {
    this.disableFieldsOnEvaluate = false;
    this.spinner.show();

    this.ncgrService.clearDocs().pipe(
      finalize(() => this.spinner.hide())
    ).subscribe({
      next: () => {
        this.rfpFiles = [];
        this.proposalFiles = [];
        this.savedRfpName = null;
        this.savedProposalNames = [];
        this.evaluationResults = [];
        this.dynamicHeaders = [];

        localStorage.removeItem('evaluationResults');
        localStorage.removeItem('dynamicHeaders');
        localStorage.removeItem(this.RFP_KEY);
        localStorage.removeItem(this.PROPOSAL_KEY);

        this.toastr.success('Documents are cleared', 'Success', { positionClass: 'toast-top-right' });
      },
      error: (err) => {
        console.error('Clear Error:', err);
        this.toastr.error('Failed to clear documents', 'Error', { positionClass: 'toast-top-right' });
      }
    });
  }

  // ✅ Save file names only
  private persistFileNames() {
    if (this.savedRfpName) {
      localStorage.setItem(this.RFP_KEY, JSON.stringify(this.savedRfpName));
    } else {
      localStorage.removeItem(this.RFP_KEY);
    }

    if (this.savedProposalNames.length) {
      localStorage.setItem(this.PROPOSAL_KEY, JSON.stringify(this.savedProposalNames));
    } else {
      localStorage.removeItem(this.PROPOSAL_KEY);
    }
  }

  trackByName = (_: number, f: File) => this.norm(f.name);

}
