import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ServiceService {

  constructor(private http: HttpClient) {}

  uploadFiles(formData: FormData): Observable<any> {
    return this.http.post('http://127.0.0.1:5000/upload', formData);
  }

  evaluateDocs(formData: FormData): Observable<any> {
    return this.http.post('http://127.0.0.1:5000/evaluate', formData);
  }

  clearDocs(): Observable<any> {
    return this.http.post('http://127.0.0.1:5000/clear_all', {});
  }
}
